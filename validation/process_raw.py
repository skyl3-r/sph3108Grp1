import os
import pandas as pd


def normalize_activity_level(level_value: str) -> float:
    """Convert string values like 'Level 6' to numeric 6.0."""
    if pd.isna(level_value):
        return float('nan')
    if isinstance(level_value, (int, float)):
        return float(level_value)
    text = str(level_value).strip().lower()
    if text.startswith('level'):
        try:
            return float(text.split()[1])
        except Exception:
            pass
    # fallback: take first number in string
    import re
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    raise ValueError(f"Unknown activity level format: {level_value}")


def activity_label(avg_activity: float) -> str:
    """Assign categorical label based on average activity numeric score."""
    if pd.isna(avg_activity):
        return 'Unknown'
    if avg_activity <= 3.0:
        return 'Minimal'
    if avg_activity <= 5.0:
        return 'Low'
    if avg_activity <= 7.0:
        return 'Moderate'
    if avg_activity <= 10.0:
        return 'High'
    return 'Very High'

def activity_label_veryhigh(avg_activity: float) -> int:
    """Assign categorical label based on average activity numeric score."""
    if pd.isna(avg_activity):
        return 0
    if avg_activity <= 10.0:
        return 0
    return 1

def state_monthly_activity(path: str = None) -> pd.DataFrame:
    """Read raw_influenza.csv and return state, month, avg activity, and label for Dec/Jan/Feb."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'raw_influenza.csv')

    df = pd.read_csv(path, dtype=str)

    # Standardize column names
    df.columns = [c.strip().upper() for c in df.columns]
    if 'ACTIVITY LEVEL' not in df.columns and 'ACTIVITY LEVEL' not in df.columns:
        raise RuntimeError('Input CSV must contain ACTIVITY LEVEL column')

    # Work with state and date
    df = df.rename(columns={
        'STATENAME': 'state',
        'ACTIVITY LEVEL': 'activity_level',
        'ACTIVITY LEVEL LABEL': 'activity_label_source',
        'WEEKEND': 'weekend',
    })

    # Numeric column
    df['activity_numeric'] = df['activity_level'].apply(normalize_activity_level)

    # Parse month from WEEKEND column
    df['weekend'] = pd.to_datetime(df['weekend'], errors='coerce')
    df['month_num'] = df['weekend'].dt.month
    month_map = {12: 'Dec', 1: 'Jan', 2: 'Feb'}
    df['month'] = df['month_num'].map(month_map)

    # Keep only Dec-Jan-Feb
    df = df[df['month'].notna()].copy()

    # Aggregate by state + month
    agg = (
        df.groupby(['state', 'month'], as_index=False)
        .agg(avg_activity=('activity_numeric', 'mean'))
    )
    agg['avg_activity'] = agg['avg_activity'].round(3)
    agg['activity_label'] = agg['avg_activity'].apply(activity_label)
    agg['isVeryHigh'] = agg['avg_activity'].apply(activity_label_veryhigh)

    return agg[['state', 'month', 'avg_activity', 'activity_label', 'isVeryHigh']].sort_values(['state', 'month'])


US_STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'District of Columbia': 'DC',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL',
    'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
}


def state_monthly_to_status_csv(
    source_df: pd.DataFrame,
    out_path: str = None,
    seed_state: str = 'LA',
    season_year: int = 2024,
) -> pd.DataFrame:
    """Convert monthly state activity to infection status CSV readable by US_plot.py."""
    df = source_df.copy()

    month_to_year_month = {'Dec': f'{season_year}-12', 'Jan': f'{season_year + 1}-01', 'Feb': f'{season_year + 1}-02'}
    df['year_month'] = df['month'].map(month_to_year_month)
    df['abbrev'] = df['state'].map(US_STATE_ABBREV)
    missing = sorted(df[df['abbrev'].isna()]['state'].unique())
    if missing:
        print(f"Warning: dropping states with no abbreviation mapping: {missing}")
    df = df[df['abbrev'].notna()].copy()

    if 'isVeryHigh' not in df.columns:
        raise ValueError("Expected source DataFrame to have 'isVeryHigh' column")

    df['infected'] = df['isVeryHigh'].astype(int)
    df['seed_state'] = seed_state

    status_df = df[['year_month', 'abbrev', 'infected', 'seed_state']].sort_values(['year_month', 'abbrev'])

    if out_path is None:
        out_path = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'state_infection_validation.csv')

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    status_df.to_csv(out_path, index=False)
    return status_df


if __name__ == '__main__':
    result = state_monthly_activity()
    out_file = os.path.join(os.path.dirname(__file__), 'state_month_influenza.csv')
    result.to_csv(out_file, index=False)
    print(f'Saved state monthly average influenza activity (Dec/Jan/Feb) to: {out_file}')
    print(result.head(40).to_string(index=False))

    status_file = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'state_infection_validation.csv')
    status_result = state_monthly_to_status_csv(result, out_path=status_file, seed_state='LA')
    print(f'Saved US_plot-compatible infection status to: {status_file}')
    print(status_result.head(40).to_string(index=False))
