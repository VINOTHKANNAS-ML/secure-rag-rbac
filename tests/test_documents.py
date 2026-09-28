"""Tests for UI document uploads (RBAC rules, extraction, delete permissions)."""

import base64
import io
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import documents
from src.rbac import get_role


class FakeCollection:
    def __init__(self):
        self.added = []
        self.deleted_where = []

    def add(self, ids, documents, metadatas):
        self.added.append((ids, documents, metadatas))

    def delete(self, where):
        self.deleted_where.append(where)


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def make_docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


BODY = "This is a sufficiently long test document body about quarterly planning."


class TestDocuments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        documents.DOCS_DIR = os.path.join(self.tmp, "documents")
        documents.METADATA_PATH = os.path.join(self.tmp, "metadata.json")
        self.col = FakeCollection()

    def upload(self, role, username="u", dept="HR", level=1, name="a.txt", content=None, title="T"):
        return documents.add_document(
            self.col, get_role(role), username, name,
            content if content is not None else b64(BODY), title, dept, level)

    def test_upload_within_access_is_indexed_and_listed(self):
        res = self.upload("hr_manager", "aisha", "HR", 2)
        self.assertEqual(len(self.col.added), 1)
        meta = self.col.added[0][2][0]
        self.assertEqual((meta["department"], meta["confidentiality_level"]), ("HR", 2))
        rows = documents.list_documents(get_role("hr_manager"), "aisha")
        self.assertEqual([r["doc_id"] for r in rows], [res["doc_id"]])
        self.assertTrue(rows[0]["can_delete"])

    def test_cannot_upload_above_own_level(self):
        with self.assertRaises(documents.UploadError):
            self.upload("hr_manager", "aisha", "HR", 3)
        self.assertEqual(self.col.added, [])

    def test_cannot_upload_into_other_department(self):
        with self.assertRaises(documents.UploadError):
            self.upload("hr_manager", "aisha", "Finance", 1)

    def test_intern_cannot_upload(self):
        with self.assertRaises(documents.UploadError):
            self.upload("intern", "priya", "General", 0)

    def test_others_do_not_see_uploads_above_their_access(self):
        self.upload("hr_manager", "aisha", "HR", 2)
        self.assertEqual(documents.list_documents(get_role("employee"), "arjun"), [])
        self.assertEqual(len(documents.list_documents(get_role("admin"), "admin.root")), 1)

    def test_delete_permissions(self):
        # engineering manager uploads; an Engineering employee can SEE it
        # (Internal level) but did not upload it, so must not delete it.
        res = self.upload("engineering_manager", "wei", "Engineering", 1)
        self.assertEqual(len(documents.list_documents(get_role("employee"), "arjun")), 1)
        self.assertFalse(documents.list_documents(get_role("employee"), "arjun")[0]["can_delete"])
        with self.assertRaises(PermissionError):
            documents.delete_document(self.col, get_role("employee"), "arjun", res["doc_id"])
        self.assertEqual(self.col.deleted_where, [])
        # the uploader can delete it
        documents.delete_document(self.col, get_role("engineering_manager"), "wei", res["doc_id"])
        self.assertEqual(self.col.deleted_where, [{"doc_id": res["doc_id"]}])
        self.assertEqual(documents.list_documents(get_role("admin"), "x"), [])

    def test_admin_can_delete_anyones_upload(self):
        res = self.upload("hr_manager", "aisha", "HR", 2)
        documents.delete_document(self.col, get_role("admin"), "admin.root", res["doc_id"])
        self.assertEqual(documents.list_documents(get_role("admin"), "admin.root"), [])

    def test_hidden_document_looks_nonexistent(self):
        res = self.upload("hr_manager", "aisha", "HR", 2)
        with self.assertRaises(KeyError):
            documents.delete_document(self.col, get_role("employee"), "arjun", res["doc_id"])

    def test_bad_extension_rejected(self):
        with self.assertRaises(documents.UploadError):
            self.upload("hr_manager", "aisha", name="virus.exe")

    def test_docx_text_extracted(self):
        content = base64.b64encode(make_docx(BODY)).decode()
        self.upload("hr_manager", "aisha", name="policy.docx", content=content)
        self.assertIn("quarterly planning", self.col.added[0][1][0])

    def test_too_large_and_empty_rejected(self):
        big = base64.b64encode(b"a" * (documents.MAX_FILE_BYTES + 1)).decode()
        with self.assertRaises(documents.UploadError):
            self.upload("hr_manager", "aisha", content=big)
        with self.assertRaises(documents.UploadError):
            self.upload("hr_manager", "aisha", content=b64("hi"))

    def test_options_reflect_role(self):
        opts = documents.upload_options(get_role("hr_manager"))
        self.assertEqual(set(opts["departments"]), {"General", "HR"})
        self.assertEqual(max(l["value"] for l in opts["levels"]), 2)
        self.assertFalse(documents.upload_options(get_role("intern"))["allowed"])


if __name__ == "__main__":
    unittest.main()
