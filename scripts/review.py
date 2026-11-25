"""Mechanical note checks; semantic support and visual reading remain with the author."""
import re
import unicodedata


def fold(s):
    return " ".join(unicodedata.normalize("NFKC",s).casefold().split())


def measured(row,refs,db):
    m=row.get("measurement")
    if not m:return
    if row["state"]!="supported":raise ValueError("use separate alternatives for an unresolved value")
    by_role={r.get("role"):r for r in refs}
    if not {"row","header","caption","condition"}<=by_role.keys():raise ValueError("a table measurement needs row, header, caption and condition evidence")
    header,data,caption=[by_role[k] for k in ("header","row","caption")]
    if not (header["doc"]==data["doc"]==caption["doc"]):raise ValueError("mixed sources for a table cell")
    if header["page"]!=data["page"] or header["view"]!="layout" or data["view"]!="layout":
        raise ValueError("use a same-page layout header/row pair, or record a visually checked result without automatic cell binding")
    if not m.get("condition") or not m.get("unit") or fold(m["unit"]) not in fold(caption["quote"]):
        raise ValueError("table measurement needs condition and unit anchored to caption")
    lines=db["documents"][data["doc"]]["pages"][data["page"]-1]["layout"]
    if header["lines"][0]!=header["lines"][1] or data["lines"][0]!=data["lines"][1]:raise ValueError("cell binding requires a single physical header line and data line")
    top=lines[header["lines"][0]-1];bottom=lines[data["lines"][0]-1]
    # Double blanks separate layout columns. Single blanks may be part of a label.
    cells=list(re.finditer(r"\S(?:.*?\S)?(?= {2,}|\s*$)",top))
    targets=[k for k,c in enumerate(cells) if fold(c[0])==fold(m["column"])]
    if len(targets)!=1 or len(cells)<2:raise ValueError("ambiguous column heading")
    if fold(m["row_label"]) not in fold(data["quote"]):raise ValueError("row label does not match evidence")
    k=targets[0];centres=[(s.start()+s.end())/2 for s in cells]
    vals=[v for v in re.finditer(r"\S+",bottom) if min(range(len(centres)),key=lambda j:abs((v.start()+v.end())/2-centres[j]))==k]
    if [v[0] for v in vals]!=[str(m["value"])]:raise ValueError("value is not the selected table cell: "+m["column"])
    if str(m["value"]) not in row["claim"]:raise ValueError("value missing from claim")


def contract_errors(value,schema,path="result"):
    if not isinstance(schema,dict):return []
    types={"string":str,"number":(int,float),"integer":int,"array":list,"object":dict,"boolean":bool,"null":type(None)}
    t=schema.get("type")
    if isinstance(t,str) and t in types and (not isinstance(value,types[t]) or t in ("number","integer") and isinstance(value,bool)):
        return [path+" expected "+t]
    errors=[]
    if isinstance(value,dict):
        for k in schema.get("required",schema.get("required_result_fields",[])):
            if k not in value or value[k] is None:errors.append(path+"."+k+" missing")
        for k,sub in schema.get("properties",{}).items():
            if k in value:errors+=contract_errors(value[k],sub,path+"."+k)
    if isinstance(value,list):
        if len(value)<schema.get("minItems",0):errors.append(path+" too short")
        for i,item in enumerate(value):
            errors+=contract_errors(item,schema.get("items"),f"{path}[{i}]")
    return errors


def enrich(result,draft,db):
    allowed={"supported","not_reported","uncertain","conflicting","unreadable"}
    notes=result["notes"];ids=set();terms={};aliases=draft.get("aliases",{})
    for n in notes:
        nid=n.get("id","")
        if not re.fullmatch(r"[A-Za-z0-9_-]+",nid) or nid in ids:raise ValueError("unsafe or repeated note id: "+nid)
        ids.add(nid)
        if n["state"] not in allowed:raise ValueError("unknown evidence state")
        if n["state"]!="supported" and not n.get("basis"):raise ValueError("a gap needs a reason and scope checked")
        if n["state"]=="conflicting" and len({(r["doc"],r["page"],tuple(r["lines"])) for r in n["evidence"]})<2:raise ValueError("conflict requires two different source positions")
        if n["state"]=="supported" and not n["evidence"]:raise ValueError("missing evidence")
        measured(n,n["evidence"],db)
        for tag in n.get("tags",[]):
            k=fold(aliases.get(tag,tag))
            bucket=terms.setdefault(k,{"aliases":[],"note_ids":[]})
            if tag not in bucket["aliases"]:bucket["aliases"].append(tag)
            if nid not in bucket["note_ids"]:bucket["note_ids"].append(nid)
    result["knowledge_index"]=terms
    result["section_notes"]=[{"section":s,"note_ids":[n["id"] for n in notes if n["section"]==s]} for s in result["sections"]]
    card={}
    for field,note_ids in draft.get("card",{}).items():
        if not isinstance(note_ids,list) or not note_ids or not set(note_ids)<=ids:raise ValueError("invalid card references: "+field)
        card[field]=[{"note_id":n["id"],"claim":n["claim"],"state":n["state"]} for n in notes if n["id"] in note_ids]
    result["paper_card"]=card


def assess_contract(result,draft,db):
    views={}
    for key,val in draft.get("contract_fields",{}).items():
        if key in ("case_id","output_contract","sources","status","notes","sections","title","changes","uncertainties","generated_views"):raise ValueError("reserved field: "+key)
        if key in ("paper_card","section_notes","knowledge_index"):views[key]=result[key]
        result[key]=val
    if views:result["generated_views"]=views
    contract=result["output_contract"]
    if isinstance(contract,list):schema={"required":[k for k in contract if isinstance(k,str)]}
    elif isinstance(contract,dict) and not set(contract).intersection({"required","required_result_fields","properties","type"}):
        schema={"required":[k for k in contract if k not in ("files","artifacts","description")]}
    else:schema=contract
    gaps=contract_errors(result,schema)
    notes=result["notes"]
    if any(n["state"] in ("conflicting","unreadable","uncertain") for n in notes):
        gaps.append("Unresolved findings; see per-note basis.")
    if not notes:gaps.append("No notes could be verified.")
    if not db["documents"]:gaps.append("No readable source document.")
    if result["status"] not in ("success","partial","failed","unable_to_determine"):raise ValueError("unknown case status")
    if gaps and result["status"]=="success":result["status"]="partial"
    result["uncertainties"].extend(gaps)
