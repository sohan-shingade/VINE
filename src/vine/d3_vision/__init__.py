"""D3 — plant-health computer vision on multispectral imagery.

Tasks: plant-stress classification, pest/disease detection, yield regression.
Fine-tunes a pretrained CNN (ResNet-50 / EfficientNet-B0) with a 7-channel
input adapter. NDVI thresholding provides weak pseudo-labels when annotated
imagery is scarce.
"""
