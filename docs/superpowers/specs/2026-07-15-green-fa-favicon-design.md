# Green 發 favicon design

## Goal

Add a recognizable browser favicon for 牌运 (Haiun) that reflects its Mahjong focus.

## Design

The icon is a traditional Mahjong tile: a warm ivory rounded rectangle with a fine charcoal outline and a centered deep-green 發 character. It uses a transparent canvas so the tile remains clear against browser tab themes.

The ICO contains 16px, 32px, and 48px square raster variants. The mark is simplified at small sizes: no shadows, glints, or extra decoration.

## Integration

Store the asset at `frontend/public/favicon.ico` and reference it from `frontend/index.html`. No product copy, application behavior, or translations change.

## Validation

Confirm the ICO contains the required image sizes and that the production frontend build succeeds with the favicon reference.
