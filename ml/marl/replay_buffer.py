import random
import numpy as np
from collections import deque, namedtuple
from typing import Tuple, List

Transition = namedtuple('Transition', ['state', 'action', 'reward', 'next_state', 'done'])

class ReplayBuffer:
    """Experience replay buffer for storing and sampling transitions."""
    
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
        
    def push(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool) -> None:
        """Store a new transition in the buffer."""
        self.buffer.append(Transition(state, action, reward, next_state, done))
        
    def sample(self, batch_size: int = 32) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Sample a batch of transitions uniformly at random.
        
        Returns:
            Tuple of (states, actions, rewards, next_states, dones) as numpy arrays.
        """
        transitions = random.sample(self.buffer, batch_size)
        
        # Unpack the list of namedtuples into separate lists
        batch = Transition(*zip(*transitions))
        
        states = np.array(batch.state)
        actions = np.array(batch.action)
        rewards = np.array(batch.reward)
        next_states = np.array(batch.next_state)
        dones = np.array(batch.done)
        
        return states, actions, rewards, next_states, dones
        
    def __len__(self) -> int:
        """Return the current number of transitions in the buffer."""
        return len(self.buffer)
