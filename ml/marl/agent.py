import os
import torch
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import json
from typing import Optional, List, Dict, Any

from .networks import QNetwork
from .replay_buffer import ReplayBuffer

class MARLAgent:
    """MARL DQN Agent for traffic signal control."""
    
    def __init__(self, state_dim: int, action_dim: int, junction_id: str, config: dict = None):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.junction_id = junction_id
        self.config = config or {}
        
        # Device configuration
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Networks
        self.policy_net = QNetwork(state_dim, action_dim).to(self.device)
        self.target_net = QNetwork(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        # Optimizer
        self.lr = self.config.get("lr", 0.001)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.lr)
        
        # Replay Buffer
        capacity = self.config.get("buffer_capacity", 10000)
        self.memory = ReplayBuffer(capacity)
        
        # Hyperparameters
        self.epsilon = self.config.get("epsilon", 1.0)
        self.epsilon_min = self.config.get("epsilon_min", 0.01)
        self.epsilon_decay = self.config.get("epsilon_decay", 0.995)
        self.gamma = self.config.get("gamma", 0.99)
        self.batch_size = self.config.get("batch_size", 32)
        self.target_update_freq = self.config.get("target_update_freq", 100)
        
        # Counters and metrics
        self.step_counter = 0
        self.episode_counter = 0
        self.metrics = {
            "episode_rewards": [],
            "losses": [],
            "epsilon_history": []
        }
        
    def select_action(self, state: np.ndarray, valid_actions: List[int] = None) -> int:
        """Select an action using epsilon-greedy policy with optional action masking."""
        # Exploration
        if np.random.random() < self.epsilon:
            if valid_actions is not None and len(valid_actions) > 0:
                return np.random.choice(valid_actions)
            return np.random.randint(self.action_dim)
            
        # Exploitation
        self.policy_net.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor).cpu().numpy().flatten()
            
            if valid_actions is not None and len(valid_actions) > 0:
                # Mask invalid actions with large negative value
                masked_q_values = np.full(self.action_dim, -np.inf)
                for a in valid_actions:
                    masked_q_values[a] = q_values[a]
                return int(np.argmax(masked_q_values))
                
            return int(np.argmax(q_values))
            
    def store_transition(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        """Push transition to replay buffer."""
        self.memory.push(state, action, reward, next_state, done)
        
    def train_step(self) -> Optional[float]:
        """Perform one training step of the DQN."""
        if len(self.memory) < self.batch_size:
            return None
            
        # Sample batch
        states, actions, rewards, next_states, dones = self.memory.sample(self.batch_size)
        
        states_tensor = torch.FloatTensor(states).to(self.device)
        actions_tensor = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        rewards_tensor = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states_tensor = torch.FloatTensor(next_states).to(self.device)
        dones_tensor = torch.FloatTensor(dones).unsqueeze(1).to(self.device)
        
        self.policy_net.train()
        
        # Current Q values
        current_q = self.policy_net(states_tensor).gather(1, actions_tensor)
        
        # Target Q values
        with torch.no_grad():
            next_q = self.target_net(next_states_tensor).max(1)[0].unsqueeze(1)
            target_q = rewards_tensor + (self.gamma * next_q * (1 - dones_tensor))
            
        # Compute loss
        loss = F.mse_loss(current_q, target_q)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping
        for param in self.policy_net.parameters():
            if param.grad is not None:
                param.grad.data.clamp_(-1, 1)
        self.optimizer.step()
        
        loss_val = loss.item()
        self.metrics["losses"].append(loss_val)
        
        self.step_counter += 1
        
        # Update target network
        if self.step_counter % self.target_update_freq == 0:
            self.update_target_network()
            
        # Decay epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        self.metrics["epsilon_history"].append(self.epsilon)
        
        return loss_val
        
    def update_target_network(self):
        """Copy weights from policy to target network."""
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
    def calculate_reward(self, state: dict) -> float:
        """Compute reward based on junction state."""
        # state expected to have: queue_lengths, delays, weights, phase_switched
        q_m = state.get("queue_lengths", [])
        d_m = state.get("delays", [])
        w_m = state.get("weights", [1.0] * len(q_m))
        
        alpha = 0.5
        beta = 2.0
        
        # Check if phase was switched
        is_switch = state.get("phase_switched", False)
        I_switch = 1.0 if is_switch else 0.0
        
        # Sum of weighted queue lengths
        queue_penalty = sum(w * q for w, q in zip(w_m, q_m))
        
        # Sum of delays
        delay_penalty = sum(d_m)
        
        reward = -(queue_penalty + alpha * delay_penalty) - beta * I_switch
        
        # Normalize reward loosely
        normalized_reward = np.clip(reward / 100.0, -1.0, 1.0)
        return float(normalized_reward)
        
    def get_valid_actions(self, state_info: dict) -> List[int]:
        """Action masking based on safety constraints."""
        phase_elapsed = state_info.get("phase_elapsed", 0.0)
        min_green = 10.0
        max_green = 60.0
        
        # Action 0: Extend, Action 1: Switch
        if phase_elapsed < min_green:
            return [0]
        elif phase_elapsed >= max_green:
            return [1]
        else:
            return [0, 1]
            
    def save(self, path: str):
        """Save agent checkpoint."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        checkpoint = {
            'policy_net_state_dict': self.policy_net.state_dict(),
            'target_net_state_dict': self.target_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'step_counter': self.step_counter,
            'episode_counter': self.episode_counter,
            'metrics': self.metrics
        }
        torch.save(checkpoint, path)
        
    def load(self, path: str):
        """Load agent checkpoint."""
        if not os.path.exists(path):
            return
            
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
        self.target_net.load_state_dict(checkpoint['target_net_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.epsilon = checkpoint['epsilon']
        self.step_counter = checkpoint.get('step_counter', 0)
        self.episode_counter = checkpoint.get('episode_counter', 0)
        self.metrics = checkpoint.get('metrics', self.metrics)
        
    def get_metrics(self) -> dict:
        """Return training history."""
        return self.metrics
