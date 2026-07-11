from src.urp_plugin import descriptor


def test_descriptor_name():
    assert descriptor()["name"] == "local-s3-adapter"
