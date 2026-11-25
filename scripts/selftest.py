"""Run the synthetic example and perturb each independent relationship once."""
import copy
import json
from pathlib import Path
import tempfile
from notes import index, build, read, render, ledger


def test(source,draft):
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp)
        index(source,work,None)
        db=read(work/"index.json");case=read(source/"case.json")
        result=build(case,db,draft)
        assert result["status"]=="success" and len(result["section_notes"])==3
        assert all(s["heading_evidence"]["lines"] for s in result["section_notes"])
        assert result["knowledge_index"]["warm-up"]["note_ids"]==["protocol","warm"]
        assert "evidence.md#warm-1" in render(result) and 'id="warm-1"' in ledger(result)
        assert result==build(case,db,draft)
        for label,mutate in [
            ("neighboring column",lambda d:d["notes"][2]["measurement"].update(column="Cold")),
            ("wrong page",lambda d:d["notes"][1]["evidence"][0].update(page=2)),
            ("duplicate note ID",lambda d:d["notes"][1].update(id="warm")),
            ("missing unit source",lambda d:d["notes"][2]["evidence"].pop(2)),
            ("dangling card entry",lambda d:d["card"].update(extra=["unknown"])),
            ("unjustified gap",lambda d:d["notes"][4].pop("basis")),
        ]:
            modified=copy.deepcopy(draft);mutate(modified)
            try:build(case,db,modified)
            except ValueError:pass
            else:raise AssertionError("accepted "+label)
        altered=copy.deepcopy(case);altered["output_contract"]["required"].append("author_email")
        assert build(altered,db,draft)["status"]=="partial"
        print("PASS: complete example, heading anchors, alias retrieval, ledger links, deterministic output, 6 rejected mutations and missing-field partial.")


if __name__=="__main__":
    base=Path(__file__).resolve().parents[1]/"examples"
    test(base/"input",read(base/"draft.json"))
