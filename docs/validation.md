# Week 4 Validation Matrix

## Standard error shape
```json
{"status":422,"error":"Medicine name is required","field":"name"}
```

Create/update validation covers medicines, suppliers, customers and sales. Invalid input returns 422; forbidden deletes return 403.

## Break-it tests
| Test | Expected |
|---|---|
| Missing medicine name | 422 |
| Non-numeric price | 422 |
| Negative stock | 422 |
| Missing supplier | 422 |
| Quantity exceeds stock | 422 |
| Invalid payment method | 422 |
| Unauthorized delete | 403 |
