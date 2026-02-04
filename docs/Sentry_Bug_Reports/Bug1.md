# AttributeError: 'Request' object has no attribute 'mode'

**Link:** https://geeked-out-games.sentry.io/issues/7240399386/

**Culprit:** `/api/simulate-quarter`

## Message

Failed to load game state for 698287728651e0cfb5a55be7

## Metadata

```
{
  "filename": "BackEnd/api/api.py",
  "function": "simulate_quarter_endpoint",
  "in_app_frame_mix": "in-app-only",
  "type": "AttributeError",
  "value": "'Request' object has no attribute 'mode'"
}
```
