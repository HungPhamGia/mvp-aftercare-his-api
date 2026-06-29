"""Live self-check: hits the real Supabase DB through the app.

Run: python test_app.py   (needs DATABASE_URL in .env and a reachable DB)
Read-only — fetches existing records, writes nothing.
"""
import warnings

warnings.filterwarnings("ignore")  # silence httpx/testclient deprecation noise

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PHI_FORBIDDEN = {"so_the_bhyt", "chan_doan", "xet_nghiem"}
EXPECTED_FETCH_KEYS = {
    "ho_ten", "phau_thuat", "ngay_xuat_vien", "lich_tai_kham", "bac_si_phu_trach",
}


def test_connection_lists_records():
    r = client.get("/records")
    assert r.status_code == 200, r.text
    recs = r.json()
    assert isinstance(recs, list) and recs, "no records returned from live DB"
    assert {"ma_ho_so", "ho_ten", "phau_thuat", "ngay_xuat_vien", "tier"} <= recs[0].keys()
    return recs


def test_patient_fetch_real_record():
    mhs = test_connection_lists_records()[0]["ma_ho_so"]
    r = client.post("/his/patient/fetch", json={"set_variables": {"ma_ho_so": mhs}})
    assert r.status_code == 200, r.text
    sv = r.json()["set_variables"]
    assert set(sv) == EXPECTED_FETCH_KEYS, set(sv)
    assert PHI_FORBIDDEN.isdisjoint(sv), f"PHI leaked: {PHI_FORBIDDEN & set(sv)}"
    assert sv["ho_ten"], "real record should have a name"


def test_full_record_and_history():
    mhs = test_connection_lists_records()[0]["ma_ho_so"]
    r = client.get(f"/records/{mhs}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["record"]["ma_ho_so"] == mhs
    assert "latest_call_result" in body
    # history endpoint returns a list (possibly empty)
    h = client.get(f"/records/{mhs}/call-results")
    assert h.status_code == 200 and isinstance(h.json(), list)


def test_unknown_record_404():
    r = client.post("/his/patient/fetch", json={"set_variables": {"ma_ho_so": "DOES-NOT-EXIST"}})
    assert r.status_code == 404, r.text


if __name__ == "__main__":
    recs = test_connection_lists_records()
    test_patient_fetch_real_record()
    test_full_record_and_history()
    test_unknown_record_404()
    print(f"ok - live DB reachable, {len(recs)} record(s)")
