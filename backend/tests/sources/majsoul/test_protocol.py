from app.sources.majsoul.protocol import descriptor_url


def test_descriptor_url_supports_current_nested_resource_manifest():
    manifest = {"res": {"res/proto/liqi.json": {"prefix": "v0.11.252.w"}}}
    assert descriptor_url("0.11.252.w", manifest) == (
        "https://game.maj-soul.com/1/v0.11.252.w/res/proto/liqi.json"
    )
