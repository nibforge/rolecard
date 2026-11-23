import json

import pytest

from rolecard import get_db
from rolecard.models import Document, Job
from rolecard.services import documents as docs
from rolecard.services.jobs import create_job
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE
from tests.test_documents import CV, LETTER, OFFER
from tests.test_jobs_views import provider


@pytest.fixture
def job_id(app):
    with app.app_context():
        return create_job(get_db(), text=OFFER, url="", title="Dev", company="Pagos").id


@pytest.fixture
def with_profile(app):
    with app.app_context():
        save_profile(get_db(), PROFILE)


def generate(client, csrf, app, kind="cv", answer=CV, **extra):
    provider(app, [json.dumps(answer)])
    return client.post(f"/jobs/1/documents/{kind}", data={"csrf_token": csrf, **extra})


def doc(app, kind="cv") -> Document:
    with app.app_context():
        found = get_db().query(Document).filter_by(kind=kind).one()
        get_db().expunge(found)
        return found


def act(client, csrf, sid, action, text="", kind="letter", hx=False):
    headers = {"HX-Request": "true"} if hx else {}
    return client.post(f"/jobs/1/documents/{kind}/sentences/{sid}", headers=headers,
                       data={"csrf_token": csrf, "action": action, "text": text})


def test_generate_redirects_to_review(client, csrf, app, job_id, with_profile):
    resp = generate(client, csrf, app)
    assert resp.status_code == 302 and resp.location.endswith("/jobs/1/documents/cv")
    page = client.get("/jobs/1/documents/cv").get_data(as_text=True)
    assert "Built billing APIs." in page and "experience.0.highlights.0" in page


def test_generate_without_profile_goes_to_profile(client, csrf, app, job_id):
    resp = generate(client, csrf, app)
    assert resp.status_code == 302 and resp.location.endswith("/profile")


def test_generate_without_provider_goes_to_settings(client, csrf, app, job_id, with_profile):
    app.config["AI_PROVIDER_FACTORY"] = lambda: None
    resp = client.post("/jobs/1/documents/cv", data={"csrf_token": csrf})
    assert resp.status_code == 302 and resp.location.endswith("/settings")


def test_existing_document_goes_to_review_unless_replace(client, csrf, app, job_id,
                                                         with_profile):
    generate(client, csrf, app)
    resp = generate(client, csrf, app, answer={**CV, "skills": [1]})
    assert resp.location.endswith("/jobs/1/documents/cv")
    assert doc(app).content["blocks"][-2]["items"] != ["SQL"]
    generate(client, csrf, app, answer={**CV, "skills": [1]}, replace="1")
    assert doc(app).content["blocks"][-2]["items"] == ["SQL"]


def test_ai_error_flashes_and_saves_nothing(client, csrf, app, job_id, with_profile):
    provider(app, ["not json"])
    resp = client.post("/jobs/1/documents/cv", data={"csrf_token": csrf})
    assert resp.location.endswith("/jobs/1")
    assert "alerta-error" in client.get("/jobs/1").get_data(as_text=True)
    with app.app_context():
        assert get_db().query(Document).count() == 0


@pytest.mark.parametrize("url", ["/jobs/1/documents/cv", "/jobs/1/documents/memo",
                                 "/jobs/9/documents/cv"])
def test_missing_review_is_404(client, job_id, url):
    assert client.get(url).status_code == 404


def test_review_shows_unsourced_reason_and_escapes(client, csrf, app, job_id, with_profile):
    hostile = {"paragraphs": [[{"text": "<script>x</script> I am a guru.", "sources": []}]]}
    generate(client, csrf, app, "letter", hostile)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert "frase-unsourced" in page and "the AI gave no source" in page
    assert "<script>x" not in page and "&lt;script&gt;x" in page
    assert "Export is blocked: some sentences have no source" in page


def test_review_warns_when_profile_changed(client, csrf, app, job_id, with_profile):
    generate(client, csrf, app)
    changed = json.loads(json.dumps(PROFILE))
    changed["experience"][0]["highlights"] = ["Built payment APIs"]
    with app.app_context():
        save_profile(get_db(), changed)
    before = doc(app).content
    page = client.get("/jobs/1/documents/cv").get_data(as_text=True)
    assert "Your profile has changed" in page and "the profile has changed" in page
    assert doc(app).content == before  # a GET shows the refreshed state but never writes


def test_sentence_actions_htmx_return_document(client, csrf, app, job_id, with_profile):
    generate(client, csrf, app, "letter", LETTER)
    resp = act(client, csrf, "s2", "confirm", hx=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200 and body.lstrip().startswith('<div id="documento">')
    assert "<html" not in body and "frase-confirmed" in body
    act(client, csrf, "s1", "edit", "Your payments platform.", hx=True)
    resp = act(client, csrf, "s2", "delete")
    assert resp.status_code == 302
    sentences = doc(app, "letter").content["sentences"]
    assert [s["state"] for s in sentences.values()] == ["edited", "deleted"]
    assert sentences["s1"]["text"] == "Your payments platform."


@pytest.mark.parametrize(("sid", "action"), [("s9", "confirm"), ("s1", "eval"),
                                             ("s1", "edit")])
def test_bad_sentence_action_is_400(client, csrf, app, job_id, with_profile, sid, action):
    generate(client, csrf, app, "letter", LETTER)
    assert act(client, csrf, sid, action).status_code == 400


def test_mark_reviewed_blocked_then_cv_prepares_job(client, csrf, app, job_id, with_profile):
    generate(client, csrf, app, "letter", LETTER)
    url = "/jobs/1/documents/{}/review"
    assert client.post(url.format("letter"), data={"csrf_token": csrf}).status_code == 400
    generate(client, csrf, app)
    resp = client.post(url.format("cv"), data={"csrf_token": csrf})
    assert resp.status_code == 302 and doc(app).reviewed_at is not None
    with app.app_context():
        assert get_db().get(Job, 1).status == "prepared"
    assert "Ready to export" in client.get("/jobs/1/documents/cv").get_data(as_text=True)


def test_job_page_buttons_and_language(client, csrf, app, job_id, with_profile):
    provider(app, [])
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "Prepare CV" in page and "Prepare cover letter" in page
    generate(client, csrf, app)
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "View CV" in page and "Prepare cover letter" in page
    assert "sentences to review" in page or "Not marked as reviewed" in page
    resp = client.post("/jobs/1/language", data={"csrf_token": csrf, "language": "es"})
    assert resp.status_code == 302
    with app.app_context():
        assert docs.doc_language(get_db().get(Job, 1), "en") == "es"
    bad = client.post("/jobs/1/language", data={"csrf_token": csrf, "language": "fr"})
    assert bad.status_code == 400


def test_job_page_without_profile_explains(client, job_id):
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "You need a profile and an AI provider" in page and "Prepare CV" not in page


def reviewed(client, csrf, app, kind="cv", answer=CV):
    generate(client, csrf, app, kind, answer)
    if kind == "letter":
        act(client, csrf, "s1", "confirm")
        act(client, csrf, "s2", "confirm")
    client.post(f"/jobs/1/documents/{kind}/review", data={"csrf_token": csrf})


@pytest.mark.parametrize("suffix", [".pdf", "/print"])
def test_exports_blocked_until_reviewed(client, csrf, app, job_id, with_profile, suffix):
    generate(client, csrf, app, "letter", LETTER)
    resp = client.get(f"/jobs/1/documents/letter{suffix}")
    assert resp.status_code == 409 and "have no source" in resp.get_data(as_text=True)
    act(client, csrf, "s2", "confirm")
    resp = client.get(f"/jobs/1/documents/letter{suffix}")
    assert resp.status_code == 409 and "cite only the offer" in resp.get_data(as_text=True)
    act(client, csrf, "s1", "confirm")
    resp = client.get(f"/jobs/1/documents/letter{suffix}")
    assert resp.status_code == 409 and "mark the document as reviewed" in resp.get_data(
        as_text=True)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert "Download PDF" not in page and "data-copy" not in page


def test_cv_pdf_download_with_safe_name(client, csrf, app, job_id, with_profile):
    with app.app_context():
        found = get_db().get(Job, 1)
        found.company, found.title = 'Pagós "SL"/../', "Dev <Backend>"
        get_db().commit()
    reviewed(client, csrf, app)
    resp = client.get("/jobs/1/documents/cv.pdf")
    assert resp.status_code == 200 and resp.mimetype == "application/pdf"
    assert resp.headers["Content-Disposition"] == (
        'attachment; filename="cv-pagos-sl-dev-backend.pdf"')
    assert resp.data.startswith(b"%PDF")
    assert "Download PDF" in client.get("/jobs/1/documents/cv").get_data(as_text=True)


def test_letter_copy_and_print_view(client, csrf, app, job_id, with_profile):
    reviewed(client, csrf, app, "letter", LETTER)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert 'data-copy="texto-carta"' in page and "I am a Rust guru." in page
    resp = client.get("/jobs/1/documents/letter/print")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "print.css" in body and "<form" not in body
    assert "Kind regards," in body and "I am a Rust guru." in body
    pdf = client.get("/jobs/1/documents/letter.pdf")
    assert pdf.headers["Content-Disposition"].endswith('cover-letter-pagos-dev.pdf"')


def test_review_warns_about_substitutions(client, csrf, app, job_id, with_profile):
    hostile = {"paragraphs": [[{"text": "Moved to Łódź.", "sources": ["offer"]}]]}
    generate(client, csrf, app, "letter", hostile)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert "cannot go in the PDF" in page and "Ł ź" in page


def test_offer_only_sentence_must_be_confirmed_to_export(client, csrf, app, job_id,
                                                         with_profile):
    offer_only = {"paragraphs": [[{"text": "Your 1500 payments per second.",
                                   "sources": ["offer"]}]]}
    generate(client, csrf, app, "letter", offer_only)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert "frase-oferta" in page and "confirm it to export" in page
    assert "It is true, I take it" in page and "data-copy" not in page
    assert "Mark as reviewed" not in page
    review = client.post("/jobs/1/documents/letter/review", data={"csrf_token": csrf})
    assert review.status_code == 400
    for suffix in (".pdf", "/print"):
        assert client.get(f"/jobs/1/documents/letter{suffix}").status_code == 409
    act(client, csrf, "s1", "confirm")
    client.post("/jobs/1/documents/letter/review", data={"csrf_token": csrf})
    assert client.get("/jobs/1/documents/letter.pdf").status_code == 200
    assert client.get("/jobs/1/documents/letter/print").status_code == 200
    assert "data-copy" in client.get("/jobs/1/documents/letter").get_data(as_text=True)
    generate(client, csrf, app, "letter", offer_only, replace="1")
    assert client.get("/jobs/1/documents/letter.pdf").status_code == 409


def test_pending_offer_sentences_are_counted_open_and_unlock_one_by_one(
        client, csrf, app, job_id, with_profile):
    letter = {"paragraphs": [[{"text": "Your payment platform.", "sources": ["offer"]},
                              {"text": "Your team in Madrid.", "sources": ["offer"]}]]}
    generate(client, csrf, app, "letter", letter)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert "Pending sentences: 2." in page
    assert page.count('<details class="frase-detalle" open>') == 2
    body = act(client, csrf, "s1", "confirm", hx=True).get_data(as_text=True)
    assert "Pending sentences: 1." in body and "Mark as reviewed" not in body
    body = act(client, csrf, "s2", "edit", text="Your team.", hx=True).get_data(as_text=True)
    assert "Pending sentences" not in body and "Mark as reviewed" in body
    assert body.count('<details class="frase-detalle" open>') == 0
    client.post("/jobs/1/documents/letter/review", data={"csrf_token": csrf})
    assert client.get("/jobs/1/documents/letter.pdf").status_code == 200


def test_review_has_one_block_notice_progress_and_side_panel(client, csrf, app, job_id,
                                                               with_profile):
    letter = {"paragraphs": [[{"text": "Your payment platform.", "sources": ["offer"]}]]}
    generate(client, csrf, app, "letter", letter)
    page = client.get("/jobs/1/documents/letter").get_data(as_text=True)
    assert page.count("rc-callout--danger") == 1 and "0 of 1 sentences verified" in page
    assert 'class="rail rc-inspector-rail"' in page and 'data-editor="s1"' in page
    assert 'href="#editar-s1" data-sentence="s1" data-pending' in page
