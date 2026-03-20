"""
代码审查记录 - Code Review Record

用于 Dev Agent 和 Review Agent 之间的交流
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ReviewComment:
    """审查评论"""

    id: str
    file_path: str
    line: int | None
    severity: str  # critical, major, minor, suggestion
    message: str
    status: str = "open"  # open, resolved, rejected
    author: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: str | None = None
    response: str | None = None


@dataclass
class ReviewRecord:
    """审查记录"""

    id: str
    title: str
    status: str = "pending"  # pending, in_progress, approved, rejected
    comments: list[ReviewComment] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = ""
    assignee: str = ""


class ReviewManager:
    """审查管理器 - Dev 和 Review 代理的交流桥梁"""

    def __init__(self, review_dir: str = "./reviews"):
        self.review_dir = Path(review_dir)
        self.review_dir.mkdir(parents=True, exist_ok=True)

    def create_review(
        self, title: str, created_by: str = "dev", assignee: str = "review"
    ) -> str:
        """创建审查"""
        import uuid

        review_id = f"review_{uuid.uuid4().hex[:8]}"

        record = ReviewRecord(
            id=review_id, title=title, created_by=created_by, assignee=assignee
        )

        self._save_review(record)
        return review_id

    def add_comment(
        self,
        review_id: str,
        file_path: str,
        line: int | None,
        severity: str,
        message: str,
        author: str,
    ) -> None:
        """添加评论"""
        record = self._load_review(review_id)

        import uuid

        comment = ReviewComment(
            id=f"comment_{uuid.uuid4().hex[:8]}",
            file_path=file_path,
            line=line,
            severity=severity,
            message=message,
            author=author,
        )

        record.comments.append(comment)
        record.updated_at = datetime.now().isoformat()
        self._save_review(record)

    def resolve_comment(self, review_id: str, comment_id: str, response: str) -> None:
        """解决评论（Dev 修复后）"""
        record = self._load_review(review_id)

        for comment in record.comments:
            if comment.id == comment_id:
                comment.status = "resolved"
                comment.response = response
                comment.resolved_at = datetime.now().isoformat()
                break

        record.updated_at = datetime.now().isoformat()
        self._save_review(record)

    def reject_comment(self, review_id: str, comment_id: str, reason: str) -> None:
        """拒绝评论"""
        record = self._load_review(review_id)

        for comment in record.comments:
            if comment.id == comment_id:
                comment.status = "rejected"
                comment.response = reason
                break

        record.updated_at = datetime.now().isoformat()
        self._save_review(record)

    def update_status(self, review_id: str, status: str) -> None:
        """更新审查状态"""
        record = self._load_review(review_id)
        record.status = status
        record.updated_at = datetime.now().isoformat()
        self._save_review(record)

    def get_review(self, review_id: str) -> ReviewRecord:
        """获取审查记录"""
        return self._load_review(review_id)

    def list_reviews(
        self, status: str | None = None, assignee: str | None = None
    ) -> list[dict]:
        """列出审查"""
        reviews = []

        for file in self.review_dir.glob("*.json"):
            with open(file) as f:
                record = json.load(f)

            if status and record.get("status") != status:
                continue
            if assignee and record.get("assignee") != assignee:
                continue

            reviews.append(record)

        return reviews

    def get_summary(self, review_id: str) -> dict:
        """获取审查摘要"""
        record = self._load_review(review_id)

        open_comments = sum(1 for c in record["comments"] if c["status"] == "open")
        resolved = sum(1 for c in record["comments"] if c["status"] == "resolved")
        rejected = sum(1 for c in record["comments"] if c["status"] == "rejected")

        critical = sum(1 for c in record["comments"] if c["severity"] == "critical")
        major = sum(1 for c in record["comments"] if c["severity"] == "major")

        return {
            "id": review_id,
            "title": record["title"],
            "status": record["status"],
            "open_comments": open_comments,
            "resolved": resolved,
            "rejected": rejected,
            "critical_issues": critical,
            "major_issues": major,
            "can_merge": open_comments == 0 and critical == 0,
        }

    def _save_review(self, record: ReviewRecord) -> None:
        """保存审查记录"""
        file_path = self.review_dir / f"{record.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_review(self, review_id: str) -> ReviewRecord:
        """加载审查记录"""
        file_path = self.review_dir / f"{review_id}.json"
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return ReviewRecord(**data)


# 全局实例
_review_manager: ReviewManager | None = None


def get_review_manager() -> ReviewManager:
    """获取审查管理器"""
    global _review_manager
    if _review_manager is None:
        _review_manager = ReviewManager()
    return _review_manager
