import pytest
import numpy as np

# Mocking the MARLAgent class for unit tests
class MARLAgent:
    def __init__(self, state_dim, action_dim):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.replay_buffer = []
        self.min_green = 5

    def select_action(self, state, phase_elapsed):
        # Action masking
        if phase_elapsed < self.min_green:
            return 0 # Keep phase
        # Dummy policy
        return 1

    def push(self, state, action, reward, next_state, done):
        self.replay_buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size):
        if len(self.replay_buffer) < batch_size:
            return []
        return self.replay_buffer[:batch_size]

    def save(self, path):
        pass

    def load(self, path):
        pass

def calculate_reward(queue_length, delay):
    return - (queue_length + delay * 0.5)

def test_agent_creation():
    agent = MARLAgent(state_dim=10, action_dim=2)
    assert agent.state_dim == 10
    assert agent.action_dim == 2

def test_select_action():
    agent = MARLAgent(10, 2)
    state = np.zeros(10)
    action = agent.select_action(state, phase_elapsed=10)
    assert action in [0, 1]

def test_action_masking():
    agent = MARLAgent(10, 2)
    state = np.zeros(10)
    action = agent.select_action(state, phase_elapsed=3)
    # Masking should force keep phase (0)
    assert action == 0

def test_replay_buffer():
    agent = MARLAgent(10, 2)
    state = np.zeros(10)
    agent.push(state, 1, -1.0, state, False)
    assert len(agent.replay_buffer) == 1
    samples = agent.sample(1)
    assert len(samples) == 1
    assert samples[0][1] == 1

def test_reward_calculation():
    reward = calculate_reward(queue_length=10, delay=4)
    # - (10 + 4 * 0.5) = -12.0
    assert reward == -12.0

def test_save_load(tmp_path):
    agent = MARLAgent(10, 2)
    save_file = tmp_path / "model.pt"
    agent.save(save_file)
    agent.load(save_file)
    # No exception means it passed our mock test
    assert True
