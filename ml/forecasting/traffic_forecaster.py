import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from xgboost import XGBRegressor
import os
import joblib
from typing import Dict, Any, List

# Local imports
from .feature_engineering import create_sequences, engineer_features, normalize_data, denormalize_data

class TrafficLSTM(nn.Module):
    """
    LSTM model for processing sequential traffic data.
    """
    def __init__(self, input_size: int = 1, hidden_size: int = 128, num_layers: int = 2, output_size: int = 1):
        super(TrafficLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out


class TrafficForecaster:
    """
    LSTM + XGBoost ensemble traffic forecasting model.
    """
    def __init__(self, lstm_hidden_size=128, lstm_layers=2, sequence_length=24, forecast_horizons=[3, 6, 12]):
        self.sequence_length = sequence_length
        self.forecast_horizons = forecast_horizons
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # The output size is the max horizon we predict, we'll index into it to get specific horizons
        self.max_horizon = max(self.forecast_horizons)
        self.lstm_model = TrafficLSTM(
            input_size=1, 
            hidden_size=lstm_hidden_size, 
            num_layers=lstm_layers, 
            output_size=self.max_horizon
        ).to(self.device)
        
        self.xgb_models = {h: XGBRegressor(n_estimators=100, max_depth=6) for h in self.forecast_horizons}
        
        self.is_lstm_trained = False
        self.is_xgb_trained = False
        
        self.min_val = 0.0
        self.max_val = 1.0

    def train_lstm(self, train_data: np.ndarray, epochs=50, lr=0.001, batch_size=32) -> list:
        norm_data, self.min_val, self.max_val = normalize_data(train_data)
        
        xs, ys = [], []
        for i in range(len(norm_data) - self.sequence_length - self.max_horizon + 1):
            xs.append(norm_data[i:i + self.sequence_length])
            ys.append(norm_data[i + self.sequence_length : i + self.sequence_length + self.max_horizon])
            
        X = torch.tensor(np.array(xs), dtype=torch.float32).unsqueeze(-1)
        Y = torch.tensor(np.array(ys), dtype=torch.float32)
        
        dataset = torch.utils.data.TensorDataset(X, Y)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.lstm_model.parameters(), lr=lr)
        
        self.lstm_model.train()
        history = []
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_X, batch_Y in dataloader:
                batch_X, batch_Y = batch_X.to(self.device), batch_Y.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.lstm_model(batch_X)
                loss = criterion(outputs, batch_Y)
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item() * batch_X.size(0)
            
            history.append(epoch_loss / len(dataset))
            
        self.is_lstm_trained = True
        return history

    def train_xgboost(self, features: pd.DataFrame, targets: pd.Series):
        X = features.drop(columns=['timestamp', 'pcu_value', 'junction_id'], errors='ignore')
        
        for horizon in self.forecast_horizons:
            y = targets.shift(-horizon).dropna()
            X_h = X.iloc[:len(y)]
            self.xgb_models[horizon].fit(X_h, y)
            
        self.is_xgb_trained = True

    def predict_lstm(self, recent_sequence: np.ndarray) -> np.ndarray:
        if not self.is_lstm_trained:
            raise ValueError("LSTM model is not trained.")
            
        self.lstm_model.eval()
        norm_seq = (recent_sequence - self.min_val) / (self.max_val - self.min_val + 1e-8)
        X = torch.tensor(norm_seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(self.device)
        
        with torch.no_grad():
            outputs = self.lstm_model(X).squeeze(0).cpu().numpy()
            
        return denormalize_data(outputs, self.min_val, self.max_val)

    def predict_xgboost(self, features: pd.DataFrame) -> dict:
        if not self.is_xgb_trained:
            raise ValueError("XGBoost model is not trained.")
            
        X = features.drop(columns=['timestamp', 'pcu_value', 'junction_id'], errors='ignore').iloc[-1:]
        predictions = {}
        for horizon in self.forecast_horizons:
            predictions[horizon] = float(self.xgb_models[horizon].predict(X)[0])
            
        return predictions

    def predict_ensemble(self, recent_data: np.ndarray, features: pd.DataFrame) -> dict:
        lstm_preds = self.predict_lstm(recent_data)
        xgb_preds = self.predict_xgboost(features)
        
        ensemble_preds = {}
        for h in self.forecast_horizons:
            # lstm_preds is an array of length max_horizon, so index is h-1
            lstm_val = lstm_preds[h - 1] if (h - 1) < len(lstm_preds) else xgb_preds[h]
            ensemble_preds[h] = 0.6 * float(lstm_val) + 0.4 * xgb_preds[h]
            
        return ensemble_preds

    def predict(self, junction_id: str, recent_readings: list[dict]) -> dict:
        """
        High-level prediction endpoint.
        Returns forecasts and spillback risk.
        """
        if not self.is_lstm_trained or not self.is_xgb_trained:
            raise ValueError("Models are not fully trained yet.")
            
        if len(recent_readings) < self.sequence_length:
            raise ValueError(f"Need at least {self.sequence_length} readings for prediction.")
            
        df = pd.DataFrame(recent_readings)
        recent_pcu = df['pcu_value'].values[-self.sequence_length:]
        
        features_df = engineer_features(df)
        
        ensemble_preds = self.predict_ensemble(recent_pcu, features_df)
        
        horizons_res = []
        for h, pred_val in ensemble_preds.items():
            horizons_res.append({
                "minutes": h * 5,
                "predicted_pcu": float(max(0, pred_val)),
                "confidence": 0.85 
            })
            
        avg_pred = sum(ensemble_preds.values()) / len(ensemble_preds)
        spillback_risk = self.calculate_spillback_risk(avg_pred, road_capacity_pcu=150.0)
        
        return {
            "junction_id": junction_id,
            "horizons": horizons_res,
            "spillback_risk": spillback_risk
        }

    def calculate_spillback_risk(self, predicted_pcu: float, road_capacity_pcu: float) -> float:
        risk = predicted_pcu / road_capacity_pcu
        return float(np.clip(risk, 0.0, 1.0))

    def generate_synthetic_data(self, num_days: int = 7, junctions: int = 4) -> pd.DataFrame:
        """
        Generates synthetic training data reflecting daily/weekly patterns.
        """
        periods = num_days * 24 * 12 
        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq='5min')
        
        data = []
        for j_idx in range(junctions):
            base = 50 + 20 * np.sin(2 * np.pi * timestamps.hour / 24)
            peak1 = 40 * np.exp(-0.5 * ((timestamps.hour - 9) / 1.5)**2)
            peak2 = 50 * np.exp(-0.5 * ((timestamps.hour - 18) / 1.5)**2)
            
            weekend_mask = timestamps.dayofweek.isin([5, 6]).astype(float)
            pattern = base + (peak1 + peak2) * (1 - weekend_mask * 0.5)
            
            noise = np.random.normal(0, 5, periods)
            pcu_values = np.clip(pattern + noise, 0, None)
            
            for t, pcu in zip(timestamps, pcu_values):
                data.append({
                    "timestamp": t,
                    "junction_id": f"J{j_idx+1}",
                    "pcu_value": pcu
                })
                
        return pd.DataFrame(data)

    def save_models(self, path: str):
        os.makedirs(path, exist_ok=True)
        torch.save(self.lstm_model.state_dict(), os.path.join(path, "lstm_model.pth"))
        joblib.dump(self.xgb_models, os.path.join(path, "xgb_models.pkl"))
        joblib.dump({"min": self.min_val, "max": self.max_val, "seq": self.sequence_length}, os.path.join(path, "meta.pkl"))

    def load_models(self, path: str):
        lstm_path = os.path.join(path, "lstm_model.pth")
        xgb_path = os.path.join(path, "xgb_models.pkl")
        meta_path = os.path.join(path, "meta.pkl")
        
        if os.path.exists(lstm_path) and os.path.exists(xgb_path):
            self.lstm_model.load_state_dict(torch.load(lstm_path, map_location=self.device))
            self.xgb_models = joblib.load(xgb_path)
            meta = joblib.load(meta_path)
            self.min_val = meta["min"]
            self.max_val = meta["max"]
            self.sequence_length = meta["seq"]
            self.is_lstm_trained = True
            self.is_xgb_trained = True
        else:
            raise FileNotFoundError("Model files not found.")
