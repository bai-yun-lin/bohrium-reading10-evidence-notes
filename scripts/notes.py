"""Index primary materials and compile agent-authored claims into traceable notes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from review import enrich, fold, assess_contract


def norm(text):
    return " ".join(unicodedata.normalize("NFKC",text).split())


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def pdf_pages(path,layout):
    if shutil.which("pdftotext"):
        args=["pdftotext","-enc","UTF-8"]+(["-layout"] if layout else [])+[str(path),"-"]
        p=subprocess.run(args,capture_output=True,timeout=100)
        if p.returncode: raise ValueError(p.stderr.decode("utf8","replace")[:250])
        pages=p.stdout.decode("utf8").split("\f")
        return pages[:-1] if len(pages)>1 and not pages[-1].strip() else pages
    try:
        import pymupdf
    except ImportError as exc:
        raise ValueError("PDF requires pdftotext or PyMuPDF") from exc
    with pymupdf.open(path) as d:
        if d.needs_pass: raise ValueError("PDF is encrypted")
        return [page.get_text("text",sort=layout) for page in d]


def ocr_page(path,n,work,lang):
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise ValueError("pdftoppm or tesseract unavailable")
    work.mkdir(parents=True,exist_ok=True)
    dest=work/f"page-{n}"
    subprocess.run(["pdftoppm","-f",str(n),"-l",str(n),"-singlefile","-r","220","-png",str(path),str(dest)],capture_output=True,check=True,timeout=35)
    res=subprocess.run(["tesseract",str(dest)+".png","stdout","-l",lang],capture_output=True,check=True,timeout=45)
    return res.stdout.decode("utf8","replace")


def index(root,work,chosen,lang=None):
    case=read(root/"case.json")
    paths=[root/s for s in chosen] if chosen else sorted(
        p for p in root.rglob("*") if p.suffix.lower() in (".pdf",".md",".txt") and p!=root/"task.md")
    db={"case_id":case["case_id"],"documents":{},"issues":[]}
    for i,path in enumerate(paths,1):
        if not path.resolve().is_relative_to(root.resolve()):raise ValueError("source outside case")
        doc=f"d{i}"; pages=[]
        try:
            raw=path.read_bytes()
            if path.suffix.lower()==".pdf":
                body=pdf_pages(path,False);layout=pdf_pages(path,True)
            else:
                body=raw.decode("utf-8-sig").split("\f");layout=body
            for n,(b,l) in enumerate(zip(body,layout),1):
                mode="native"
                if len(norm(b))<32 and path.suffix.lower()==".pdf":
                    issue="sparse_text_check_render"
                    if lang:
                        try:
                            transcript=ocr_page(path,n,work/doc,lang)
                            if transcript.strip():b=transcript;mode="ocr";issue="ocr_verify_glyphs_and_numbers_on_render"
                        except (OSError,ValueError,subprocess.SubprocessError) as exc:issue+="; "+str(exc)[:120]
                    db["issues"].append({"document":doc,"page":n,"issue":issue})
                pages.append({"page":n,"body":b.splitlines(),"layout":l.splitlines(),"body_method":mode})
            db["documents"][doc]={"file":path.relative_to(root).as_posix(),"sha256":hashlib.sha256(raw).hexdigest(),"pages":pages}
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            db["issues"].append({"file":str(path.name),"issue":str(exc)})
    save(work/"index.json",db)
    print(json.dumps({"documents":len(db["documents"]),"pages":sum(len(d["pages"]) for d in db["documents"].values()),"issues":db["issues"]},ensure_ascii=True))


def locate(db,ref):
    doc=db["documents"][ref["doc"]]; n=ref["page"]
    if not isinstance(n,int) or not 1<=n<=len(doc["pages"]):raise ValueError(f"invalid page: {n}")
    view=ref.get("view","body");lines=doc["pages"][n-1][view];needle=norm(ref["quote"])
    if not needle:raise ValueError("empty quote")
    hits=[]
    for i,line in enumerate(lines):
        if not line.strip():continue
        for j in range(i,min(len(lines),i+10)):
            excerpt=norm(" ".join(lines[i:j+1]))
            if needle in excerpt:
                if j==i or needle not in norm(" ".join(lines[i+1:j+1])):hits.append((i,j))
                break
    if ref.get("line"):
        hits=[(i,j) for i,j in hits if i+1==ref["line"]]
    if len(hits)!=1:raise ValueError(f"{ref['doc']} p{n}: expected one match, found {len(hits)} for {needle!r}")
    i,j=hits[0]
    if norm(" ".join(lines[i:j+1])).count(needle)!=1:raise ValueError("quote occurs twice within the same evidence span; add context")
    return dict(doc=ref["doc"],page=n,view=view,lines=[i+1,j+1],quote=ref["quote"],location=ref.get("location",""),role=ref.get("role","text"))


def build(case,db,draft):
    if not case["case_id"]==db["case_id"]==draft["case_id"]:raise ValueError("case IDs differ")
    sections=draft["sections"];rows=[]
    for row in draft["notes"]:
        bound=[locate(db,r) for r in row.get("evidence",[])]
        if row["state"]=="supported" and not bound:raise ValueError("supported note lacks evidence")
        if row["section"] not in sections:raise ValueError("unknown section")
        rows.append(dict(row,evidence=bound))
    result={"case_id":case["case_id"],"output_contract":case.get("output_contract",{}),"title":draft["title"],
            "sections":sections,"notes":rows,"sources":{k:{"file":v["file"],"sha256":v["sha256"]} for k,v in db["documents"].items()},
            "status":draft.get("status","partial"),"uncertainties":db["issues"]+draft.get("uncertainties",[]),"changes":draft.get("changes",[])}
    enrich(result,draft,db)
    for item in result["section_notes"]:
        label=item["section"]
        ref=draft.get("section_refs",{}).get(label)
        if ref:item["heading_evidence"]=locate(db,ref);continue
        matches=[(doc,page["page"],i+1) for doc,source in db["documents"].items() for page in source["pages"] for i,line in enumerate(page["body"])
                 if norm(line).lstrip("# ").rstrip()==norm(label)]
        if len(matches)==1:
            doc,page,line=matches[0];item["heading_evidence"]={"doc":doc,"page":page,"view":"body","lines":[line,line],"quote":label}
        else:
            result["uncertainties"].append({"section":label,"issue":"heading not uniquely matched; provide section_refs or explain document structure"})
            if result["status"]=="success":result["status"]="partial"
    assess_contract(result,draft,db)
    return result


def render(result):
    md=["# "+result["title"],""]
    for section in result["sections"]:
        md+=["## "+section,""]
        for row in result["notes"]:
            if row["section"]!=section:continue
            refs=", ".join(f"[{r['location'] or r['doc']} · p.{r['page']} · {r['view']} L{r['lines'][0]}–{r['lines'][1]}](evidence.md#{row['id']}-{i})" for i,r in enumerate(row["evidence"],1))
            md.extend([f"<a id=\"{row['id']}\"></a>",f"- **{row['kind']}** {row['claim']} ({refs or row['state']})",""])
            if row.get("basis"):md.extend(["  "+row["basis"],""])
    md.extend(["## 检索",""])
    for term,entry in result.get("generated_views",{}).get("knowledge_index",result["knowledge_index"]).items():
        md.append("- "+term+" · "+", ".join(f"[{n}](#{n})" for n in entry["note_ids"]))
    return "\n".join(md)


def ledger(result):
    lines=["# 原文核验索引",""]
    for note in result["notes"]:
        for i,r in enumerate(note["evidence"],1):
            s=result["sources"][r["doc"]]
            lines.extend([f'<a id="{note["id"]}-{i}"></a>',f'### {note["id"]} · {r["role"]}',
                          f'{s["file"]} · PDF/text page {r["page"]} · {r["view"]} lines {r["lines"]} · {r["location"]}',
                          "","> "+r["quote"],"",f'来源指纹 `{s["sha256"]}`',""])
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("index","build","search"));p.add_argument("--input",type=Path,default=Path("/input"));p.add_argument("--work",type=Path,default=Path("/app/work/notes"));p.add_argument("--output",type=Path,default=Path("/app/output"));p.add_argument("--source",action="append");p.add_argument("--draft",type=Path);p.add_argument("--ocr-lang");p.add_argument("--query");a=p.parse_args()
    if a.command=="index":index(a.input,a.work,a.source,a.ocr_lang);return
    if a.command=="search":
        if not a.query:p.error("search needs --query")
        r=read(a.output/"result.json");key=fold(a.query)
        index_terms=r.get("generated_views",{}).get("knowledge_index",r["knowledge_index"])
        ids={i for term,b in index_terms.items() if key in [fold(t) for t in [term]+b["aliases"]] for i in b["note_ids"]}
        print(json.dumps([n for n in r["notes"] if n["id"] in ids or key in fold(n["claim"])],ensure_ascii=False,indent=1));return
    result=build(read(a.input/"case.json"),read(a.work/"index.json"),read(a.draft or a.work/"draft.json"))
    a.output.mkdir(parents=True,exist_ok=True);(a.output/"notes.md").write_text(render(result),encoding="utf8")
    (a.output/"evidence.md").write_text(ledger(result),encoding="utf8")
    save(a.output/"result.json",result)


if __name__=="__main__":main()
