"""Classificador ML de schema: aprende a mapear colunas -> campos canônicos.

Pipeline:
  1. extract_features(col, series) -> vetor de features (header + conteúdo)
  2. build_training_set() usa FILES como ground truth (~54 exemplos rotulados)
  3. RandomForestClassifier prevê o campo por coluna (+ "ignore")
  4. Hungarian assignment garante 1:1 entre colunas e campos
"""
from __future__ import annotations
import re
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from scipy.optimize import linear_sum_assignment

from .config import FILES, RAW_DIR, PROCESSED_DIR

MODELS_DIR = PROCESSED_DIR.parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODELS_DIR / "schema_classifier.joblib"

# Campos que queremos descobrir
FIELDS = ["cliente", "cnpj", "uf", "data", "ean", "produto", "valor", "qtd", "canal"]

HEADER_KEYWORDS = {
    "cliente": ["cliente", "razao", "social", "nome", "fantasia", "loja"],
    "cnpj":    ["cnpj", "cpf", "documento", "doc"],
    "uf":      ["uf", "estado", "est"],
    "data":    ["data", "dt", "dia", "emissao"],
    "ean":     ["ean", "barras", "barra", "codigo", "cod"],
    "produto": ["produto", "descricao", "descrição", "desc", "item", "mercadoria"],
    "valor":   ["valor", "vlr", "total", "preco", "faturamento"],
    "qtd":     ["qtd", "quant", "un", "unid", "volume", "vol"],
    "canal":   ["canal", "painel", "segmento"],
}

UF_SET = {
    "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB",
    "PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
}
CANAL_KW = ["VAREJO", "DIRETO", "INDIRETO", "ATACADO", "ECOMM", "DISTRIBUI", "FARMA "]

EXCEL_EPOCH = pd.Timestamp("1899-12-30")


# --------------------------- features ---------------------------

def _norm_header(h: str) -> set[str]:
    h = re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()
    return set(h.split())


def extract_features(col_name, series: pd.Series) -> dict:
    s = series.dropna()
    n = max(len(s), 1)
    s_str = s.astype(str)
    h_tokens = _norm_header(col_name)

    feats = {}
    # 1) flags de keyword no header (1 por campo)
    for field, kws in HEADER_KEYWORDS.items():
        feats[f"hdr_{field}"] = int(
            any(any(kw in t or t in kw for t in h_tokens) for kw in kws)
        )

    # 2) features de conteúdo
    nums = pd.to_numeric(s, errors="coerce")
    pct_num = float(nums.notna().mean())
    feats["pct_num"] = pct_num

    valid = nums.dropna()
    if len(valid):
        is_int = valid.apply(lambda x: float(x).is_integer())
        feats["pct_int"] = float(is_int.mean())
        feats["num_mean"] = float(valid.mean())
        feats["num_std"] = float(valid.std() or 0.0)
        feats["num_max"] = float(valid.max())
        feats["num_min"] = float(valid.min())
        # dígitos quando inteiros
        digit_lens = valid[is_int].apply(lambda x: len(str(int(x))))
        if len(digit_lens):
            feats["pct_len14"]    = float((digit_lens == 14).mean())
            feats["pct_len12_13"] = float(digit_lens.between(12, 13).mean())
            feats["pct_len8_14"]  = float(digit_lens.between(8, 14).mean())
        else:
            feats["pct_len14"] = feats["pct_len12_13"] = feats["pct_len8_14"] = 0.0
    else:
        feats["pct_int"] = feats["num_mean"] = feats["num_std"] = 0.0
        feats["num_max"] = feats["num_min"] = 0.0
        feats["pct_len14"] = feats["pct_len12_13"] = feats["pct_len8_14"] = 0.0

    # serial Excel (intervalo típico de datas modernas)
    feats["pct_excel_serial"] = float(
        valid.between(30000, 80000).sum() / n
    ) if len(valid) else 0.0

    # data parseável
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        feats["pct_date"] = float(dt.notna().mean())
    except Exception:
        feats["pct_date"] = 0.0

    # estatísticas de string
    lens = s_str.str.len()
    feats["mean_len"] = float(lens.mean()) if len(lens) else 0.0
    feats["max_len"] = float(lens.max()) if len(lens) else 0.0
    feats["distinct_ratio"] = float(s.nunique() / n)

    # padrões textuais
    upper = s_str.str.upper().str.strip()
    feats["pct_uf"] = float(upper.isin(UF_SET).mean())
    feats["pct_canal_kw"] = float(
        upper.apply(lambda x: any(k in x for k in CANAL_KW)).mean()
    )

    # heurística monetária: floats com decimais, magnitude moderada
    money = (pct_num > 0.9) and (feats["pct_int"] < 0.5) and (1 < feats["num_mean"] < 100_000)
    feats["money_like"] = float(money)

    # produto: textos longos e diversos
    feats["product_like"] = float(feats["mean_len"] > 18 and feats["distinct_ratio"] > 0.05)

    return feats


# --------------------------- treino ---------------------------

def build_training_set():
    X_rows, y = [], []
    for fname, (_, mapping) in FILES.items():
        df = pd.read_excel(RAW_DIR / fname)
        col_to_field = {v: k for k, v in mapping.items() if v}
        for col in df.columns:
            X_rows.append(extract_features(col, df[col]))
            y.append(col_to_field.get(col, "ignore"))
    X = pd.DataFrame(X_rows).fillna(0.0)
    return X, np.array(y)


def train(verbose: bool = True):
    X, y = build_training_set()
    model = RandomForestClassifier(
        n_estimators=300, max_depth=None, class_weight="balanced",
        random_state=42, n_jobs=-1,
    )
    # CV honesta (com folds reduzidos por causa do dataset pequeno)
    if verbose:
        try:
            skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
            scores = cross_val_score(model, X, y, cv=skf, scoring="accuracy")
            print(f"[schema_ml] CV accuracy: {scores.mean():.3f} ± {scores.std():.3f}  (n={len(y)})")
        except ValueError as e:
            print(f"[schema_ml] CV pulada ({e})")
    model.fit(X, y)
    joblib.dump({"model": model, "feature_cols": list(X.columns)}, MODEL_PATH)
    if verbose:
        print(f"[schema_ml] modelo salvo em {MODEL_PATH.relative_to(MODELS_DIR.parent.parent)}")
    return model, list(X.columns)


def load_or_train():
    if MODEL_PATH.exists():
        b = joblib.load(MODEL_PATH)
        return b["model"], b["feature_cols"]
    return train(verbose=False)


# --------------------------- inferência ---------------------------

def predict_mapping(df: pd.DataFrame, threshold: float = 0.20) -> tuple[dict, dict]:
    """Retorna (mapping field->col, confidences field->prob)."""
    model, feat_cols = load_or_train()
    cols = list(df.columns)

    rows = [extract_features(c, df[c]) for c in cols]
    X = pd.DataFrame(rows).reindex(columns=feat_cols).fillna(0.0)
    proba = model.predict_proba(X)  # [n_cols, n_classes]
    classes = list(model.classes_)

    # restringir a campos canônicos (excluir "ignore" da otimização)
    field_classes = [c for c in classes if c != "ignore"]
    field_idx = [classes.index(f) for f in field_classes]
    score = proba[:, field_idx]  # maior = melhor

    # Hungarian: minimiza custo => negar score; padding para matriz quadrada
    n_cols, n_fields = score.shape
    size = max(n_cols, n_fields)
    pad = np.zeros((size, size))
    pad[:n_cols, :n_fields] = -score
    row_ind, col_ind = linear_sum_assignment(pad)

    mapping, conf = {}, {}
    for r, c in zip(row_ind, col_ind):
        if r >= n_cols or c >= n_fields:
            continue
        prob = float(score[r, c])
        if prob >= threshold:
            field = field_classes[c]
            mapping[field] = cols[r]
            conf[field] = prob
    return mapping, conf


# --------------------------- validação ---------------------------

def validate():
    """Re-prevê as 6 planilhas conhecidas e compara com o gabarito."""
    train(verbose=True)
    total_fields = 0
    total_correct = 0
    print(f"\n{'arquivo':<20} {'campo':<10} {'esperado':<22} {'previsto':<22} {'prob':>6}  status")
    print("-" * 95)
    for fname, (_, gt) in FILES.items():
        df = pd.read_excel(RAW_DIR / fname)
        pred, conf = predict_mapping(df)
        for field, gt_col in gt.items():
            if not gt_col:
                continue
            total_fields += 1
            p = pred.get(field)
            ok = p == gt_col
            total_correct += int(ok)
            status = "OK" if ok else "MISS"
            print(f"{fname:<20} {field:<10} {str(gt_col):<22} {str(p):<22} {conf.get(field,0):>6.2f}  {status}")
    print("-" * 95)
    print(f"acurácia por campo: {total_correct}/{total_fields} = {total_correct/total_fields:.1%}")


if __name__ == "__main__":
    validate()
