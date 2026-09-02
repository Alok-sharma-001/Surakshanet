import os
import threading
import numpy as np
from typing import List, Dict, Any, Optional

from .agent import MARLAgent

class MARLCoordinator:
    """Multi-agent coordinator for distributed traffic signals."""
    
    def __init__(self, junction_ids: List[str], state_dim: int = 8, action_dim: int = 2):
        self.junction_ids = junction_ids
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Initialize agents
        self.agents = {
            jid: MARLAgent(state_dim, action_dim, jid)
            for jid in junction_ids
        }
        
        self.is_training = False
        self._lock = threading.Lock()
        
    def step(self, junction_states: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        """Select actions for all junctions given their current states."""
        actions = {}
        for jid, state_info in junction_states.items():
            if jid in self.agents:
                agent = self.agents[jid]
                valid_actions = agent.get_valid_actions(state_info)
                # Extract vector state representation for NN
                vector_state = state_info.get("vector", np.zeros(self.state_dim))
                action = agent.select_action(vector_state, valid_actions)
                actions[jid] = action
        return actions
        
    def update(self, junction_id: str, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        """Store transition and train a specific agent."""
        if junction_id in self.agents:
            agent = self.agents[junction_id]
            agent.store_transition(state, action, reward, next_state, done)
            agent.train_step()
            
    def train_episode(self, env) -> Dict[str, Any]:
        """Run one complete episode of training in the environment."""
        env.reset()
        
        episode_rewards = {jid: 0.0 for jid in self.junction_ids}
        total_delay = 0.0
        steps = 0
        max_steps = 3600  # e.g., 1 hour simulated at 1s resolution
        
        while steps < max_steps:
            # Get states from environment
            states_info = env.get_states()
            if not states_info:
                break
                
            # Select actions
            actions = self.step(states_info)
            
            # Apply actions
            env.step(actions)
            
            # Get next states and rewards
            next_states_info = env.get_states()
            dones = env.get_dones()
            
            for jid in self.junction_ids:
                if jid in states_info and jid in next_states_info and jid in actions:
                    agent = self.agents[jid]
                    
                    # Calculate reward
                    reward = agent.calculate_reward(next_states_info[jid])
                    episode_rewards[jid] += reward
                    
                    total_delay += sum(next_states_info[jid].get("delays", []))
                    
                    vector_state = states_info[jid].get("vector", np.zeros(self.state_dim))
                    next_vector_state = next_states_info[jid].get("vector", np.zeros(self.state_dim))
                    done = dones.get(jid, False) or (steps >= max_steps - 1)
                    
                    # Store and train
                    self.update(jid, vector_state, actions[jid], reward, next_vector_state, done)
            
            steps += 1
            if all(dones.values()):
                break
                
        # Record metrics
        avg_reward = np.mean(list(episode_rewards.values()))
        for jid, agent in self.agents.items():
            agent.metrics["episode_rewards"].append(episode_rewards[jid])
            agent.episode_counter += 1
            
        return {
            "total_reward": avg_reward,
            "avg_delay": total_delay / (steps * len(self.junction_ids)) if steps > 0 else 0,
            "throughput": env.get_throughput() if hasattr(env, 'get_throughput') else 0
        }
        
    def train(self, env, num_episodes: int = 500, callback=None) -> Dict[str, Any]:
        """Train all agents for a number of episodes."""
        self.set_training_flag(True)
        history = {"rewards": [], "delays": [], "throughputs": []}
        
        try:
            for episode in range(num_episodes):
                if not self.get_training_status()["is_training"]:
                    break
                    
                metrics = self.train_episode(env)
                
                history["rewards"].append(metrics["total_reward"])
                history["delays"].append(metrics["avg_delay"])
                history["throughputs"].append(metrics["throughput"])
                
                if callback:
                    callback(episode, metrics)
                    
        finally:
            self.set_training_flag(False)
            
        return history
        
    def save_all(self, directory: str):
        """Save checkpoints for all agents."""
        os.makedirs(directory, exist_ok=True)
        for jid, agent in self.agents.items():
            path = os.path.join(directory, f"agent_{jid}.pt")
            agent.save(path)
            
    def load_all(self, directory: str):
        """Load checkpoints for all agents."""
        if not os.path.exists(directory):
            return
        for jid, agent in self.agents.items():
            path = os.path.join(directory, f"agent_{jid}.pt")
            agent.load(path)
            
    def get_training_status(self) -> Dict[str, Any]:
        """Get global training status."""
        with self._lock:
            epsilons = {jid: agent.epsilon for jid, agent in self.agents.items()}
            return {
                "is_training": self.is_training,
                "avg_epsilon": np.mean(list(epsilons.values())) if epsilons else 1.0,
                "episodes_completed": max([a.episode_counter for a in self.agents.values()]) if self.agents else 0
            }
            
    def set_training_flag(self, flag: bool):
        """Safely update training flag."""
        with self._lock:
            self.is_training = flag
