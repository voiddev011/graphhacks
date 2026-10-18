"""LoCoMo category-aware F1, ported from snap-research/locomo task_eval/evaluation.py.
Reference revision: 3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376.
No BERTScore/torch download is needed for the official token-F1 path.
"""
import re
import string
from collections import Counter
from statistics import mean
from nltk.stem import PorterStemmer

_stemmer=PorterStemmer()
def normalize(text):
    text=str(text).replace(",", "").lower()
    text="".join(c for c in text if c not in set(string.punctuation))
    return " ".join(re.sub(r"\b(a|an|the|and)\b", " ", text).split())

def token_f1(prediction,reference):
    p=[_stemmer.stem(w) for w in normalize(prediction).split()]
    r=[_stemmer.stem(w) for w in normalize(reference).split()]
    common=sum((Counter(p)&Counter(r)).values())
    if not common:return 0.0
    precision,recall=common/len(p),common/len(r)
    return 2*precision*recall/(precision+recall)

def locomo_f1(prediction,reference,category):
    reference=str(reference)
    if category==3:reference=reference.split(";")[0].strip()
    if category==1:
        return mean(max(token_f1(p.strip(),r.strip()) for p in prediction.split(",")) for r in reference.split(","))
    if category in (2,3,4):return token_f1(prediction,reference)
    if category==5:return float("no information available" in prediction.lower() or "not mentioned" in prediction.lower())
    raise ValueError("Unknown LoCoMo category")
