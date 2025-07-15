import pandas as pd

file_path = r"D:\PhD\dec2025\data\processed\filtered_sub_network_data.csv"
df = pd.read_csv(file_path, delimiter=';')

# Tüm kolonlara göre duplicate
duplicates = df[df.duplicated(keep=False)]

if not duplicates.empty:
    print(f"\n⚠️ Found {len(duplicates)} duplicate rows (counting all occurrences):")
    
    # Gruplayarak detaylı göster
    grouped = duplicates.groupby(['START_OP', 'END_OP'])
    for (start, end), group in grouped:
        print(f"\n➡️ {start} → {end} (count: {len(group)})")
        print(group[['Linie', 'KM START', 'KM END', 'polygon_length']])
else:
    print("✅ No duplicate rows found in the dataset!")

# İncelenecek Linie ID
given_line_id = 250

# Sadece bu Linie'yi filtrele
filtered_df = df[df['Linie'] == given_line_id]
# START_OP'a göre A-Z sıralama
filtered_df = filtered_df.sort_values('START_OP').reset_index(drop=True)

# Start_OP ve END_OP sütunlarını yazdır
if not filtered_df.empty:
    print(f"➡️ Linie {given_line_id} segments (START_OP → END_OP):")
    for _, row in filtered_df.iterrows():
        print(f"{row['START_OP']} → {row['END_OP']}")
else:
    print(f"⚠️ No rows found for Linie {given_line_id}")

