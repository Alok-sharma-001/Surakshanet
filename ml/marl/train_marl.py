import os
import sys
import logging
import torch
import numpy as np

# Ensure root repository is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ml.marl.agent import MARLAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def train_and_save_marl():
    weights_dir = os.path.join(os.path.dirname(__file__), "weights")
    os.makedirs(weights_dir, exist_ok=True)
    checkpoint_path = os.path.join(weights_dir, "marl_policy_downtown.pth")

    logger.info("Initializing MARLAgent for downtown junction...")
    # State: [queue_N, queue_E, queue_S, queue_W, speed_N, speed_E, speed_S, speed_W] -> 8 dims
    agent = MARLAgent(state_dim=8, action_dim=2, junction_id="DEL-CP-01", config={
        "lr": 0.001,
        "batch_size": 32,
        "gamma": 0.99,
        "epsilon": 1.0,
        "epsilon_decay": 0.992,
        "epsilon_min": 0.05
    })

    logger.info("Training MARL policy over 150 simulated corridor episodes...")
    for ep in range(150):
        # Simulate an episode of 60 seconds (1 second steps)
        state = np.random.uniform(5, 40, size=8).astype(np.float32)
        phase_elapsed = 0.0

        for step in range(60):
            phase_elapsed += 1.0
            state_info = {"phase_elapsed": phase_elapsed}
            valid_actions = agent.get_valid_actions(state_info)
            action = agent.select_action(state, valid_actions)

            if action == 1:  # Switch phase
                phase_elapsed = 0.0

            # Next state simulation: extending lowers queues on active approaches, increasing queues on others
            delta_queues = np.random.normal(loc=-1.0 if action == 0 else 1.0, scale=2.0, size=4)
            next_queues = np.clip(state[:4] + delta_queues, 0, 80)
            next_speeds = np.clip(45.0 - (next_queues * 0.4), 10, 60)
            next_state = np.concatenate([next_queues, next_speeds]).astype(np.float32)

            # Reward calculation
            reward_info = {
                "queue_lengths": next_queues.tolist(),
                "delays": (next_queues * 1.5).tolist(),
                "phase_switched": (action == 1)
            }
            reward = agent.calculate_reward(reward_info)
            done = (step == 59)

            agent.store_transition(state, action, reward, next_state, done)
            agent.train_step()
            state = next_state

        if (ep + 1) % 25 == 0:
            logger.info(f"Episode {ep+1}/150 complete | Epsilon: {agent.epsilon:.3f} | Steps: {agent.step_counter}")

    logger.info(f"Saving trained policy checkpoint to {checkpoint_path}...")
    agent.save(checkpoint_path)

    # Validate loading
    logger.info("Validating MARL policy checkpoint loading...")
    eval_agent = MARLAgent(state_dim=8, action_dim=2, junction_id="DEL-CP-01")
    eval_agent.load(checkpoint_path)
    test_state = np.array([25.0, 18.0, 32.0, 14.0, 22.0, 30.0, 16.0, 35.0], dtype=np.float32)
    selected_action = eval_agent.select_action(test_state, valid_actions=[0, 1])
    logger.info(f"MARL Validation Passed! Evaluated Action: {selected_action} ('Extend' if 0 else 'Switch')")

if __name__ == "__main__":
    train_and_save_marl()
