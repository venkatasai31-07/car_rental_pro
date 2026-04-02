# ============================================
# 🚀 CAR PRICE MODEL TRAINING (DATASET FIXED)
# ============================================

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib

# ============================================
# 📂 LOAD DATASET
# ============================================

df = pd.read_csv("final_car_dataset.csv")

print("\n📊 Dataset Loaded:", df.shape)
print("\nColumns:\n", df.columns)


# ============================================
# 🔄 RENAME COLUMNS → MATCH UI/API
# ============================================

df.rename(columns={

    "manufacture_year": "year",
    "km_driven": "km",
    "owner_type": "ownerType",
    "price": "selling_price"

}, inplace=True)


# ============================================
# 🧹 HANDLE MISSING VALUES
# ============================================

df.fillna({
    "company": "Unknown",
    "model": "Unknown",
    "fuel": "Petrol",
    "transmission": "Manual",
    "ownerType": "1st Owner"
}, inplace=True)

df["km"].fillna(df["km"].median(), inplace=True)
df["selling_price"].fillna(df["selling_price"].median(), inplace=True)


# ============================================
# ✅ SELECT REQUIRED FEATURES
# ============================================

df = df[
    [
        "company",
        "model",
        "year",
        "km",
        "fuel",
        "transmission",
        "ownerType",
        "selling_price"
    ]
]

print("\n✅ Training Columns:\n", df.columns)


# ============================================
# 🔐 ENCODE CATEGORICAL DATA
# ============================================

encoders = {}

cat_cols = [
    "company",
    "model",
    "fuel",
    "transmission",
    "ownerType"
]

for col in cat_cols:

    le = LabelEncoder()

    df[col] = le.fit_transform(df[col])

    encoders[col] = le

    print(f"\n🔑 {col} classes:", len(le.classes_))


# ============================================
# 📊 FEATURES & TARGET
# ============================================

X = df.drop("selling_price", axis=1)
y = df["selling_price"]

print("\nFeature Shape:", X.shape)


# ============================================
# 🌲 TRAIN MODEL
# ============================================

model = RandomForestRegressor(
    n_estimators=300,
    random_state=42,
    n_jobs=-1
)

model.fit(X, y)


# ============================================
# 💾 SAVE MODEL
# ============================================

joblib.dump(model, "ui_price_model.pkl")
joblib.dump(encoders, "ui_encoders.pkl")

print("\n🎉 Model Trained & Saved Successfully!")
