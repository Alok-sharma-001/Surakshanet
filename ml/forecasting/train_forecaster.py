import os
import sys
import logging
import torch
import numpy as np

# Ensure root repository is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ml.forecasting.traffic_forecaster import TrafficForecaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def fetch_real_readings_from_db(db_url: str):
    """Pulls genuine historical traffic readings from TimescaleDB hypertable."""
    import pandas as pd
    from sqlalchemy import create_engine, text
    sync_url = db_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    query = text("""
        SELECT timestamp, junction_id, pcu_value, vehicle_count, avg_speed, density
        FROM traffic_readings
        ORDER BY timestamp ASC
        LIMIT 10000;
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

def train_and_save_models(db_url: str = None):
    weights_dir = os.path.join(os.path.dirname(__file__), "weights")
    os.makedirs(weights_dir, exist_ok=True)

    logger.info("Initializing TrafficForecaster...")
    forecaster = TrafficForecaster(
        lstm_hidden_size=128,
        lstm_layers=2,
        sequence_length=24,
        forecast_horizons=[3, 6, 12]  # 15 min, 30 min, 60 min (at 5min resolution)
    )

    df = None
    target_db_url = db_url or os.environ.get("DATABASE_URL")
    if target_db_url:
        try:
            logger.info("Checking TimescaleDB hypertable for real historical traffic telemetry...")
            real_df = fetch_real_readings_from_db(target_db_url)
            if real_df is not None and len(real_df) >= 100:
                logger.info(f"Retraining forecaster using {len(real_df)} genuine TimescaleDB telemetry readings [source: live].")
                df = real_df
            else:
                count = len(real_df) if real_df is not None else 0
                logger.info(f"Insufficient TimescaleDB readings ({count} < 100). Synthesizing calibrated 14-day patterns [source: sim].")
        except Exception as e:
            logger.warning(f"Could not connect to TimescaleDB ({e}). Synthesizing calibrated 14-day patterns [source: sim].")

    if df is None:
        logger.info("Generating 14 days of realistic city traffic pattern data...")
        df = forecaster.generate_synthetic_data(num_days=14, junctions=4)
    
    pcu_series = df["pcu_value"]
    pcu_values = pcu_series.values

    logger.info("Training LSTM network on temporal sequences...")
    forecaster.train_lstm(pcu_values, epochs=8, batch_size=64, lr=0.005)

    logger.info("Engineering features and training XGBoost regressors...")
    from ml.forecasting.feature_engineering import engineer_features
    features_df = engineer_features(df)
    forecaster.train_xgboost(features_df, pcu_series)

    logger.info(f"Saving serialized model checkpoints to {weights_dir}...")
    forecaster.save_models(weights_dir)

    # Validate loading and test prediction
    logger.info("Validating model checkpoint persistence and inference...")
    validator = TrafficForecaster()
    validator.load_models(weights_dir)

    test_readings = df.tail(24).to_dict("records")
    prediction = validator.predict("DEL-CP-01", test_readings)

    logger.info("Forecaster validation successful!")
    logger.info(f"Sample Prediction for DEL-CP-01: {prediction['horizons']}")
    logger.info(f"Spillback Risk: {prediction['spillback_risk']}")

if __name__ == "__main__":
    train_and_save_models()
