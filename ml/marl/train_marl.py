"""
SurakshaNet MARL Training Loop (SN-012f)
========================================
Trains Multi-Agent Reinforcement Learning (DQN) policy using real SUMO TraCI
corridor simulation with SN-015 lane-area detectors.
Conforms to docs/08-marl-control.md and docs/26-phase2-remediation-plan.md §4.
"""

import argparse
import json
import logging
import os
import random
import sys
from typing import Dict, Any, Optional

import numpy as np
import torch

# Ensure root repository is in path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import DEMO_SEED
from shared.paths import resolve_repo_path
from shared.telemetry import ApproachTelemetry, JunctionTelemetry, DataSource
from shared.sumo_bootstrap import ensure_sumo_on_path
from simulation.sumo_env import SumoEnvironment
from ml.marl.agent import MARLAgent
from services.control_service.config import (
    ControlConfig,
    DEFAULT_JUNCTION_ID,
    WEIGHTS_PATH,
    CONTROL_STEP_S
)
from services.control_service.safety import SafetyEnvelope, JunctionRuntimeState
from services.control_service.state import build_state_vector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("surakshanet.train_marl")


def build_telemetry_from_sumo_state(
    junction_id: str,
    junction_state: Dict[str, Any],
    sim_time_s: float
) -> JunctionTelemetry:
    """Builds canonical JunctionTelemetry from SumoEnvironment junction state dict."""
    approaches = []
    j_appr = junction_state.get("approaches", {})
    for dir_code in ["N", "E", "S", "W"]:
        a_info = j_appr.get(dir_code, {})
        approaches.append(ApproachTelemetry(
            direction=dir_code,
            lane_ids=[],
            vehicle_count=float(a_info.get("vehicle_count", 0.0)),
            pcu=float(a_info.get("pcu", 0.0)),
            queue_length_m=float(a_info.get("queue_length_m", 0.0)),
            mean_speed_kmh=float(a_info.get("avg_speed", 35.0)),
            occupancy=float(a_info.get("occupancy", 0.0)),
            accumulated_wait_s=float(a_info.get("queue_length", 0.0) * 1.5)
        ))

    return JunctionTelemetry(
        junction_id=junction_id,
        source=DataSource.SUMO,
        approaches=approaches,
        current_phase=int(junction_state.get("current_phase", 0)),
        phase_elapsed_s=float(junction_state.get("phase_elapsed", 0.0)),
        sim_time_s=float(sim_time_s)
    )


def train_and_save_marl(
    seed: int = DEMO_SEED,
    episodes: int = 15,
    episode_duration_s: int = 120,
    junction_id: Optional[str] = None
) -> MARLAgent:
    """
    Trains MARLAgent against real SUMO simulation over genuine episodes.
    Honours caller episodes, seed, and config junction ID.
    """
    ensure_sumo_on_path()

    cfg = ControlConfig()
    target_junction = junction_id or cfg.junction_id or DEFAULT_JUNCTION_ID

    # Deterministic seeding
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    weights_dir = os.path.join(os.path.dirname(__file__), "weights")
    os.makedirs(weights_dir, exist_ok=True)
    checkpoint_path = os.path.join(weights_dir, "marl_policy_downtown.pth")
    hparams_path = os.path.join(weights_dir, "marl_hyperparameters.json")

    net_path = resolve_repo_path("simulation", "networks", "corridor.net.xml")
    rou_path = resolve_repo_path("simulation", "networks", "corridor.rou.xml")
    cfg_path = resolve_repo_path("simulation", "networks", "corridor.sumocfg")
    det_path = resolve_repo_path("simulation", "networks", "corridor.det.xml")

    hparams = {
        "lr": 0.001,
        "batch_size": 32,
        "gamma": 0.95,
        "epsilon": 1.0,
        "epsilon_decay": 0.98,
        "epsilon_min": 0.05,
        "seed": seed,
        "episodes": episodes,
        "episode_duration_s": episode_duration_s,
        "state_dim": 8,
        "action_dim": 2,
        "junction_id": target_junction,
        "simulation_network": "corridor.net.xml"
    }

    with open(hparams_path, "w", encoding="utf-8") as f:
        json.dump(hparams, f, indent=2)

    logger.info(
        f"Initializing MARLAgent: junction={target_junction}, seed={seed}, "
        f"episodes={episodes}, duration={episode_duration_s}s..."
    )
    agent = MARLAgent(state_dim=8, action_dim=2, junction_id=target_junction, config=hparams)
    envelope = SafetyEnvelope(cfg)

    step_interval = int(cfg.control_step_s)

    for ep in range(episodes):
        ep_seed = seed + ep * 1000
        random.seed(ep_seed)
        np.random.seed(ep_seed)
        torch.manual_seed(ep_seed)

        env = SumoEnvironment(
            net_file=net_path,
            route_file=rou_path,
            config_file=cfg_path,
            additional_files=[det_path],
            seed=ep_seed,
            end=episode_duration_s + 10
        )
        env.start()

        phase_start_time = 0.0
        last_phase = 0
        ep_reward = 0.0

        try:
            # Advance initial steps to populate network
            env.step(5)
            sumo_state = env.get_state()
            j_state = sumo_state.get("junctions", {}).get(target_junction, {})
            current_phase = int(j_state.get("current_phase", 0))
            last_phase = current_phase

            telem = build_telemetry_from_sumo_state(target_junction, j_state, 5.0)
            state_res = build_state_vector(telem, cfg)
            state = state_res.numpy_vector

            prev_total_queue = sum(float(a.get("pcu", 0.0)) for a in j_state.get("approaches", {}).values())

            for sim_sec in range(5, episode_duration_s, step_interval):
                phase_elapsed = max(0.0, sim_sec - phase_start_time)
                state_info = {"phase_elapsed": phase_elapsed}
                valid_actions = agent.get_valid_actions(state_info)

                action = agent.select_action(state, valid_actions)

                # Safety envelope verification
                runtime_state = JunctionRuntimeState(
                    junction_id=target_junction,
                    current_phase=last_phase,
                    phase_elapsed_s=phase_elapsed
                )
                safety_res = envelope.evaluate(action, runtime_state)

                if safety_res.applied_phase != last_phase:
                    env.set_phase(target_junction, safety_res.applied_phase)
                    last_phase = safety_res.applied_phase
                    phase_start_time = sim_sec
                env.set_phase_duration(target_junction, safety_res.applied_duration_s)

                # Advance simulation by step_interval
                next_sumo_state = env.step(step_interval)
                next_sim_time = float(next_sumo_state.get("simulation_time", sim_sec + step_interval))
                next_j_state = next_sumo_state.get("junctions", {}).get(target_junction, {})

                next_telem = build_telemetry_from_sumo_state(target_junction, next_j_state, next_sim_time)
                next_state_res = build_state_vector(next_telem, cfg)
                next_state = next_state_res.numpy_vector

                # Compute reward from actual SUMO detector readings
                approaches = next_j_state.get("approaches", {})
                queues = [float(a.get("pcu", 0.0)) for a in approaches.values()]
                delays = [float(a.get("queue_length", 0.0) * 1.5) for a in approaches.values()]
                reward_info = {
                    "queue_lengths": queues,
                    "delays": delays,
                    "previous_total_queue": prev_total_queue,
                }
                reward = agent.calculate_reward(reward_info)
                prev_total_queue = sum(queues)
                ep_reward += reward

                done = (sim_sec + step_interval >= episode_duration_s)
                agent.store_transition(state, action, reward, next_state, done)
                agent.train_step()

                state = next_state
                current_phase = last_phase
        finally:
            env.stop()

        agent.metrics["episode_rewards"].append(ep_reward)
        agent.episode_counter += 1
        logger.info(
            f"Episode {ep + 1}/{episodes} complete | Reward: {ep_reward:.2f} | "
            f"Epsilon: {agent.epsilon:.3f} | Steps: {agent.step_counter}"
        )

    logger.info(f"Saving trained policy checkpoint to {checkpoint_path}...")
    agent.save(checkpoint_path)

    # Re-write hparams with final metrics
    hparams["final_epsilon"] = round(float(agent.epsilon), 4)
    hparams["total_training_steps"] = agent.step_counter
    hparams["mean_episode_reward"] = (
        round(float(np.mean(agent.metrics["episode_rewards"])), 3)
        if agent.metrics["episode_rewards"] else 0.0
    )
    with open(hparams_path, "w", encoding="utf-8") as f:
        json.dump(hparams, f, indent=2)

    logger.info("Validating checkpoint loading...")
    eval_agent = MARLAgent(state_dim=8, action_dim=2, junction_id=target_junction)
    eval_agent.load(checkpoint_path)
    test_state = np.array([0.3, 0.4, 0.2, 0.1, 0.0, 0.25, 0.5, 0.5], dtype=np.float32)
    selected_action = eval_agent.select_action(test_state, valid_actions=[0, 1])
    logger.info(f"Checkpoint verified. Evaluated Action: {selected_action} ('Extend' if 0 else 'Switch')")

    return agent


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train MARL policy using real SUMO corridor simulation")
    parser.add_argument("--episodes", type=int, default=15, help="Number of training episodes")
    parser.add_argument("--seed", type=int, default=DEMO_SEED, help="Random seed for reproducibility")
    parser.add_argument("--duration", type=int, default=120, help="Duration per episode in seconds")
    args = parser.parse_args()

    train_and_save_marl(seed=args.seed, episodes=args.episodes, episode_duration_s=args.duration)

