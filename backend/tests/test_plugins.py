def test_list_builtin_plugins(client) -> None:
    response = client.get("/api/v1/plugins")
    assert response.status_code == 200
    names = {(item["stage"], item["name"]) for item in response.json()}
    assert ("query_transformer", "passthrough") in names
    assert ("query_transformer", "hyde") in names
    assert ("query_transformer", "rewrite") in names
    assert ("retriever", "dense") in names
    assert ("retriever", "bm25") in names
    assert ("chunker", "parent_child") in names
    assert ("chunker", "heading") in names
    assert ("grader", "crag") in names
    assert ("generator", "chat") in names
    assert ("loader", "auto") in names
    assert ("loader", "text") in names
    assert ("loader", "markup") in names
    assert ("loader", "layout") in names
    assert ("loader", "table") in names
    assert ("loader", "ocr") in names
    assert ("loader", "text_file") not in names
    loader_names = {item["name"] for item in response.json() if item["stage"] == "loader"}
    assert loader_names == {"auto", "layout", "markup", "ocr", "table", "text"}
    missing = [item["name"] for item in response.json() if not item.get("description")]
    assert missing == []
