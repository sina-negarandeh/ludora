from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

tokenizer = AutoTokenizer.from_pretrained("yangheng/deberta-v3-large-absa-v1.1")
model = AutoModelForSequenceClassification.from_pretrained("yangheng/deberta-v3-large-absa-v1.1")

text = "The components are amazing but the rulebook is terrible."
aspect1 = "Components"
aspect2 = "Rulebook"
aspect3 = "Gameplay"

inputs = tokenizer([text, text, text], [aspect1, aspect2, aspect3], return_tensors="pt", padding=True)
with torch.no_grad():
    outputs = model(**inputs)

print("ID to Label mapping:", model.config.id2label)
print("Logits shape:", outputs.logits.shape)
preds = torch.softmax(outputs.logits, dim=1)
for i, aspect in enumerate([aspect1, aspect2, aspect3]):
    print(f"Aspect: {aspect}")
    for j, val in enumerate(preds[i]):
        print(f"  {model.config.id2label[j]}: {val.item():.4f}")
