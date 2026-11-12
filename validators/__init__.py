from pathlib import Path


def add_issue(
    issues,
    rule_id,
    issue_type,
    severity,
    description,
    location=None,
    suggestion=""
):
    issues.append({
        "rule_id": rule_id,
        "issue_type": issue_type,
        "severity": severity,
        "description": description,
        "location": location or {},
        "suggestion": suggestion,
        "source": "python"
    })


def create_result(file_path, file_type, issues):
    has_critical = any(
        issue["severity"] == "critical"
        for issue in issues
    )

    has_high = any(
        issue["severity"] == "high"
        for issue in issues
    )

    status = (
        "failed" if has_critical or has_high
        else "warning" if issues
        else "passed"
    )

    return {
        "file_name": Path(file_path).name,
        "file_type": file_type,
        "status": status,
        "issue_count": len(issues),
        "issues": issues
    }