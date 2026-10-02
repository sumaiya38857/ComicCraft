import time

PAYLOAD = {
    "story_prompt": "A brave fox exploring an enchanted forest",
    "character_name": "Rusty",
    "setting": "forest",
    "tone": "dramatic",
    "art_style": "anime",
}


def _wait(client, job_id, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_health_and_index(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/")
    assert r.status_code == 200 and "Story prompt" in r.text


def test_full_api_flow(client):
    r = client.post("/api/v1/comics", json=PAYLOAD)
    assert r.status_code == 202
    job = _wait(client, r.json()["job_id"])
    assert job["state"] == "done", job
    comic = client.get(f"/api/v1/comics/{job['comic_id']}").json()
    assert len(comic["panels"]) == 5
    assert client.get(comic["panels"][0]["image_url"]).status_code == 200

    page = client.get(f"/comics/{comic['id']}")
    assert page.status_code == 200 and "Panel 1" in page.text

    pdf = client.get(f"/comics/{comic['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]
    assert client.get(f"/export-success?comic_id={comic['id']}").status_code == 200


def test_form_flow_and_restyle(client):
    r = client.post("/generate", data=PAYLOAD, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/jobs/")
    job_id = r.headers["location"].rsplit("/", 1)[1]
    assert client.get(f"/jobs/{job_id}").status_code == 200
    job = _wait(client, job_id)

    # Style-only change keeps the story (same seed + text), new images
    r = client.post(f"/comics/{job['comic_id']}/regenerate",
                    data={"tone": "dramatic", "art_style": "pixel art"}, follow_redirects=False)
    job2 = _wait(client, r.headers["location"].rsplit("/", 1)[1])
    a = client.get(f"/api/v1/comics/{job['comic_id']}").json()
    b = client.get(f"/api/v1/comics/{job2['comic_id']}").json()
    assert b["request"]["art_style"] == "pixel art"
    assert a["panels"][0]["narration"] == b["panels"][0]["narration"]
    assert a["seed"] == b["seed"]


def test_form_validation_error_rerenders(client):
    r = client.post("/generate", data={**PAYLOAD, "story_prompt": "hi"})
    assert r.status_code == 422 and "Please fix" in r.text


def test_sync_json_endpoint(client):
    r = client.post("/generate-comic/json", json=PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert len(body["layout"]) == 5 and body["pdf_url"].endswith(".pdf")
    assert client.get(body["pdf_url"]).status_code == 200


def test_unknown_comic_404_and_traversal(client):
    assert client.get("/comics/does-not-exist").status_code == 404
    assert client.get("/api/v1/comics/..%2F..%2Fetc").status_code == 404


def test_test_image_route(client):
    r = client.post("/test-image", json={"prompt": "a red fox", "art_style": "anime"})
    assert r.status_code == 200 and client.get(r.json()["image_url"]).status_code == 200
