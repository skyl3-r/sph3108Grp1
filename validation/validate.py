import os
import pandas as pd
from sklearn.metrics import accuracy_score, recall_score, precision_score, confusion_matrix


def load_predictions_and_actuals(
    pred_path: str = None,
    actual_path: str = None,
) -> pd.DataFrame:
    """
    Load predicted and actual infection status CSVs and merge them.
    
    Returns DataFrame with columns:
    - year_month, abbrev, seed_state
    - infected_pred (predicted)
    - infected_actual (actual)
    """
    if pred_path is None:
        pred_path = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'state_infection_status.csv')
    
    if actual_path is None:
        actual_path = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'state_infection_validation.csv')
    
    pred_df = pd.read_csv(pred_path)
    actual_df = pd.read_csv(actual_path)
    
    # Rename infected column in actual to avoid conflict
    actual_df = actual_df.rename(columns={'infected': 'infected_actual'})
    pred_df = pred_df.rename(columns={'infected': 'infected_pred'})
    
    # Merge on year_month and abbrev
    merged = pred_df.merge(
        actual_df[['year_month', 'abbrev', 'infected_actual']],
        on=['year_month', 'abbrev'],
        how='inner'
    )
    
    if merged.empty:
        raise ValueError("No matching records between predicted and actual CSVs")
    
    return merged


def compute_metrics(y_true: list, y_pred: list) -> dict:
    """Compute accuracy, recall, and precision."""
    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'recall': recall_score(y_true, y_pred, zero_division=0),
        'precision': precision_score(y_true, y_pred, zero_division=0),
    }
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics['tp'] = int(tp)
    metrics['tn'] = int(tn)
    metrics['fp'] = int(fp)
    metrics['fn'] = int(fn)
    return metrics


def validate_infection_predictions(
    pred_path: str = None,
    actual_path: str = None,
    output_csv: str = None,
) -> pd.DataFrame:
    """
    Compare predicted vs actual infection states.
    Compute metrics by month and overall.
    
    Returns DataFrame with results.
    """
    merged = load_predictions_and_actuals(pred_path, actual_path)
    
    # Overall metrics
    overall_metrics = compute_metrics(
        merged['infected_actual'].tolist(),
        merged['infected_pred'].tolist()
    )
    
    # Monthly metrics
    monthly_results = []
    for month in sorted(merged['year_month'].unique()):
        month_data = merged[merged['year_month'] == month]
        month_metrics = compute_metrics(
            month_data['infected_actual'].tolist(),
            month_data['infected_pred'].tolist()
        )
        month_metrics['year_month'] = month
        month_metrics['n_states'] = len(month_data)
        monthly_results.append(month_metrics)
    
    # Add overall row
    overall_metrics['year_month'] = 'OVERALL'
    overall_metrics['n_states'] = len(merged)
    monthly_results.append(overall_metrics)
    
    results_df = pd.DataFrame(monthly_results)
    results_df = results_df[['year_month', 'n_states', 'accuracy', 'recall', 'precision', 'tp', 'tn', 'fp', 'fn']]
    
    # Round metrics to 3 decimals
    for col in ['accuracy', 'recall', 'precision']:
        results_df[col] = results_df[col].round(3)
    
    if output_csv is None:
        output_csv = os.path.join(os.path.dirname(__file__), 'validation_results.csv')
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    results_df.to_csv(output_csv, index=False)
    
    return results_df


if __name__ == '__main__':
    results = validate_infection_predictions()
    print("Model Validation Results")
    print("=" * 100)
    print(results.to_string(index=False))
    print("\nResults saved to: validation/validation_results.csv")
