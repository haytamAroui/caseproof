"""Persistent Phase 3 live OCR acceptance. NEVER delete users or fixture data."""
from __future__ import annotations
import base64
import hashlib
import http.client
import io
import json
import os
from uuid import uuid4

from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import PROJECT_REF
from scripts.verify_dev_live_review_roundtrip import _request, _server_start, _server_stop
from scripts.verify_dev_live_multisource import _text_pdf
from scripts.verify_dev_live_txt_journey import success

ORG = "db0fe3b9-3bfc-4f69-b9ef-65a6949d67bc"
ROLES = {
 "owner": ("7e1e8ef5-e5d4-41a8-b8d4-5ccf3a6333bd", "Phase3Owner!2026"),
 "ungranted": ("d80ae946-9121-4da6-9770-148b4cec7bbf", "Phase3Ungranted!2026"),
 "foreign": ("eb5c2e9c-420c-48e3-9383-8b1d37862c42", "Phase3Foreign!2026"),
}

def sources():
    from docx import Document
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    d=Document()
    d.add_paragraph("Synthetic CaseProof draft. See Stuk 1 and Pièce 2.")
    b=io.BytesIO(); d.save(b)
    image=Image.new("RGB",(1500,650),"white")
    draw=ImageDraw.Draw(image)
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font=ImageFont.truetype(font_path,54)
    draw.text((80,90),"PIECE 2 SCANNED RECEIPT",fill="black",font=font)
    draw.text((80,190),"PAYMENT RECEIVED EUR 1250",fill="black",font=font)
    draw.text((80,290),"14 OCTOBER 2026",fill="black",font=font)
    scan=io.BytesIO()
    c=canvas.Canvas(scan,pagesize=(750,325))
    c.drawInlineImage(image,0,0,width=750,height=325)
    c.showPage();c.save()
    return [
      ("draft.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",b.getvalue()),
      ("inventory.txt","text/plain",b"Inventory: Stuk 1 invoice; Piece 2 scanned receipt.\n"),
      ("stuk-1-invoice.pdf","application/pdf",_text_pdf("Stuk 1 invoice EUR 1250")),
      ("piece-2-scanned-receipt.pdf","application/pdf",scan.getvalue()),
    ]

def direct(token,key,path,method="GET",payload=None,profile=None):
    con=http.client.HTTPSConnection(PROJECT_REF+".supabase.co",timeout=20)
    headers={"apikey":key,"Authorization":"Bearer "+token}
    if profile: headers["Accept-Profile"]=profile
    if payload is not None: headers["Content-Type"]="application/json"
    try:
        con.request(method,path,None if payload is None else json.dumps(payload).encode(),headers)
        res=con.getresponse();return res.status,res.read(250000)
    finally:con.close()

def crop(token,case,doc,version,box):
    path=f"/dev/live/matters/{case}/sources/{doc}/{version}/crop"
    con=http.client.HTTPConnection("127.0.0.1",8765,timeout=30)
    try:
        con.request("POST",path,json.dumps(box).encode(),{"Authorization":"Bearer "+token,"Content-Type":"application/json"})
        res=con.getresponse();return res.status,res.read(3000000)
    finally:con.close()

def main():
    if (os.getenv("CASEPROOF_PHASE3_LIVE")!="YES"
        or os.getenv("GITHUB_REF")!="refs/heads/feat/phase3-ocr-geometry-crops"
        or os.getenv("GITHUB_REPOSITORY")!="haytamAroui/caseproof"):
        raise RuntimeError("protected Phase 3 branch required")
    key=os.environ["CASEPROOF_DEV_PUBLISHABLE_KEY"]
    signin=SupabasePasswordSignin(PROJECT_REF,key)
    sessions={}
    for role,(user_id,password) in ROLES.items():
        # GoTrue fixture email suffix was randomly generated; look up only via
        # protected admin API, never SQL-write auth.users.
        admin=os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
        status,raw=direct(admin,admin,"/auth/v1/admin/users?page=1&per_page=100")
        if status!=200: raise RuntimeError(f"P3_AUTH_LIST_FAILED status={status}")
        candidates=[u for u in json.loads(raw).get("users",[]) if u.get("id")==user_id]
        if len(candidates)!=1: raise RuntimeError("P3_AUTH_USER_NOT_FOUND")
        session=signin.sign_in(PasswordCredentials(email=candidates[0]["email"],password=password))
        if str(session.user_id)!=user_id: raise RuntimeError("P3_AUTH_IDENTITY_MISMATCH")
        sessions[role]=session.access_token
    print("P3_AUTH_SIGNED: three existing persistent users",flush=True)
    proc=None
    try:
        proc=_server_start()
        owner=sessions["owner"]
        case=success(owner,"POST","/dev/live/matters",{"org_id":ORG,"name":"Persistent Phase 3 OCR acceptance","request_id":str(uuid4())})["case_id"]
        print("P3_MATTER_CREATED: "+case,flush=True)
        bundle=sources()
        metadata=[
          {"role":"draft" if name.endswith(".docx") else "inventory" if name.endswith(".txt") else "exhibit",
           "filename":name,"media_type":media,"byte_length":len(raw),
           "sha256":hashlib.sha256(raw).hexdigest()}
          for name,media,raw in bundle
        ]
        status,body=direct(owner,key,"/rest/v1/rpc/caseproof_dev_register_bundle","POST",
                           {"p_case":case,"p_request":str(uuid4()),"p_sources":metadata})
        if status!=200:
            try: detail=json.loads(body).get("message","")[:180]
            except ValueError: detail="non-json"
            raise RuntimeError(f"P3_BUNDLE_REGISTER_FAILED: {status} {detail}")
        registered=json.loads(body)["sources"]
        if len(registered)!=4:raise RuntimeError("P3_BUNDLE_INCOMPLETE")
        print("P3_BUNDLE_REGISTERED: four source identities",flush=True)
        scan=None
        for (filename,media,raw),item in zip(bundle,registered,strict=True):
            doc,version=item["document_id"],item["version_id"]
            uploaded=success(owner,"POST",f"/dev/live/matters/{case}/sources/{doc}/{version}/upload",{
                "content_base64":base64.b64encode(raw).decode()})
            if uploaded.get("verified") is not True: raise RuntimeError("P3_UPLOAD_SHA_FAILED")
            if filename.endswith("scanned-receipt.pdf"):scan=(doc,version)
            print("P3_UPLOAD_VERIFIED: "+filename,flush=True)
        print("P3_FOUR_SOURCES_UPLOADED",flush=True)
        doc,version=scan
        success(owner,"POST",f"/dev/live/matters/{case}/sources/{doc}/{version}/ingest?request_id={uuid4()}")
        print("P3_INGEST_RPC_SUCCEEDED",flush=True)
        status,raw=direct(owner,key,"/rest/v1/rpc/caseproof_signed_ocr_geometry",method="POST",
                          payload={"p_version":version,"p_page":1})
        if status!=200:raise RuntimeError(f"P3_GEOMETRY_RPC_FAILED: {status}")
        rows=json.loads(raw)
        if not rows:raise RuntimeError("P3_SIDECAR_MISSING: no persisted geometry")
        row=rows[0]
        payload=json.loads(row["payload"])
        if hashlib.sha256(row["payload"].encode()).hexdigest()!=row["geometry_sha256_hex"]:
            raise RuntimeError("P3_SIDECAR_HASH_MISMATCH")
        print("P3_SIDECAR_PERSISTED: verified signed DB read and canonical SHA",flush=True)
        words=payload.get("words",[])
        if not words:raise RuntimeError("P3_NO_OCR_WORDS")
        w=words[0]
        box={"page_number":1,**{k:w[k] for k in ("left","top","width","height")}}
        status,png=crop(owner,case,doc,version,box)
        if status!=200 or not png.startswith(bytes.fromhex("89504e470d0a1a0a")):
            raise RuntimeError(f"P3_AUTH_CROP_FAILED: {status}")
        print("P3_AUTH_CROP_PNG: 200",flush=True)
        _server_stop(proc);proc=None
        proc=_server_start()
        # Fresh login, no cached session or geometry.
        status,raw=direct(os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"],os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"],"/auth/v1/admin/users?page=1&per_page=100")
        users=json.loads(raw)["users"]
        email=next(u["email"] for u in users if u["id"]==ROLES["owner"][0])
        fresh=signin.sign_in(PasswordCredentials(email=email,password=ROLES["owner"][1])).access_token
        status,png=crop(fresh,case,doc,version,box)
        if status!=200 or not png.startswith(bytes.fromhex("89504e470d0a1a0a")):
            raise RuntimeError(f"P3_COLD_RESTART_CROP_FAILED: {status}")
        print("P3_RESTART_RELOGIN_CROP_PNG: 200",flush=True)
        # Denial checks before revocation.
        for role in ("ungranted","foreign"):
            status,body=crop(sessions[role],case,doc,version,box)
            if status not in (403,404) or body.startswith(bytes.fromhex("89504e47")):
                raise RuntimeError(f"P3_{role.upper()}_ACCESS_FAILURE: {status}")
            print(f"P3_{role.upper()}_CROP_DENIED: {status}",flush=True)
        status,body=direct(fresh,key,"/rest/v1/ocr_geometry_sidecars?select=*",profile="caseproof")
        if status==406:
            try: rejection=json.loads(body)
            except ValueError: rejection={}
            if rejection.get("code")!="PGRST106":
                raise RuntimeError(f"P3_POSTGREST_UNEXPECTED_406: {rejection.get('code')}")
        elif status not in (401,403,404):
            raise RuntimeError(f"P3_PRIVATE_POSTGREST_EXPOSED: {status}")
        print("P3_PRIVATE_POSTGREST_DENIED",flush=True)
        # Intentionally retain revoked grant row and every fixture.
        from scripts.verify_dev_live_txt_journey import admin_rpc
        # revoke RPC requires the fixture run and owner identity.
        ok=admin_rpc(os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"],"revoke",{
          "p_run":"45de000d-dd12-4d6d-990d-88225ae77297",
          "p_owner":ROLES["owner"][0],"p_case":case})
        if ok is not True:raise RuntimeError("P3_REVOKE_RPC_FAILED")
        status,body=crop(fresh,case,doc,version,box)
        if status not in (403,404) or body.startswith(bytes.fromhex("89504e47")):
            raise RuntimeError(f"P3_REVOKED_CROP_NOT_DENIED: {status}")
        print("P3_REVOKED_CROP_DENIED",flush=True)
        print("P3_ALL_NINE_STEPS_PASSED; persistent fixtures retained",flush=True)
    finally:
        if proc is not None:_server_stop(proc)

if __name__=="__main__":
    main()
