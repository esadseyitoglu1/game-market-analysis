import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

df = pd.read_csv('data/processed/steam_games_march2025.csv', low_memory=False)
df['total_reviews'] = (
    pd.to_numeric(df['positive'], errors='coerce').fillna(0) +
    pd.to_numeric(df['negative'], errors='coerce').fillna(0)
)
indie = df[df['genres'].str.contains('Indie', na=False) & (df['total_reviews'] > 0)]

print(f"Toplam indie oyun (en az 1 review): {len(indie):,}")
print()
print("Review dagilimi (percentile):")
for p in [50, 60, 70, 75, 80, 85, 90, 95]:
    val = indie['total_reviews'].quantile(p/100)
    print(f"  %{p} percentile: {val:.0f} review")
print()
print(f"Medyan review: {indie['total_reviews'].median():.0f}")
print(f"Ortalama review: {indie['total_reviews'].mean():.0f}")
