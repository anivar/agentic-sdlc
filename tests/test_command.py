from __future__ import annotations

from pathlib import Path

from agentic_sdlc import command as command_mod


def one(raw: str, cwd: Path | None = None):
    parsed = command_mod.parse(raw, cwd)
    assert len(parsed.commands) == 1, parsed.commands
    return parsed.commands[0]


def test_add_all_forms_are_detected():
    for raw in (
        "git add -A",
        "git add --all",
        "git add .",
        "git add -u",
        "git add -Av",
        "git add :/",
        "git -C /r add .",
    ):
        assert one(raw).add_all, raw


def test_add_by_path_passes():
    for raw in ("git add src/main.py docs/x.md", "git add -u src/", "git add -p lib/"):
        assert not one(raw).add_all, raw


def test_commit_flags_and_messages():
    facts = one('git commit -am "Fix the thing"')
    assert facts.is_commit and facts.commit_all and facts.texts == ["Fix the thing"]
    facts = one('git commit -sm "Signed message"')
    assert not facts.commit_all and facts.texts == ["Signed message"]
    facts = one('git commit -m "a" -m "b" --amend')
    assert facts.texts == ["a", "b"] and facts.amend
    facts = one("git commit --message=inline")
    assert facts.texts == ["inline"]
    facts = one("git commit -F -")
    assert facts.text_from_stdin
    facts = one("git commit -F /tmp/msg.txt")
    assert facts.text_files == ["/tmp/msg.txt"]
    facts = one("git commit --dry-run -m x")
    assert facts.dry_run


def test_push_targets_and_force(repo: Path):
    facts = one("git push", repo)
    assert facts.is_push and facts.targets == ["main"] and not facts.force
    facts = one("git push origin main", repo)
    assert facts.targets == ["main"]
    facts = one("git push --force origin main", repo)
    assert facts.force and facts.targets == ["main"]
    facts = one("git push -f origin feature", repo)
    assert facts.force and facts.targets == ["feature"]
    facts = one("git push origin +main", repo)
    assert facts.force and facts.targets == ["main"]
    facts = one("git push --force-with-lease origin HEAD:main", repo)
    assert facts.force and facts.targets == ["main"]
    facts = one("git push origin HEAD:refs/heads/topic", repo)
    assert facts.targets == ["topic"] and not facts.force
    facts = one("git push --delete origin main", repo)
    assert facts.deletes == ["main"]
    facts = one("git push origin :main", repo)
    assert facts.deletes == ["main"]
    facts = one("git push --mirror origin", repo)
    assert facts.force and "*" in facts.targets
    facts = one("git push -n origin main", repo)
    assert facts.dry_run


def test_push_tags(repo: Path):
    facts = one("git push --force origin refs/tags/v1.0.0", repo)
    assert facts.tags_pushed and facts.force_tags and facts.targets == []
    facts = one("git push --tags --force", repo)
    assert facts.force_tags
    facts = one("git push origin --tags", repo)
    assert facts.tags_pushed and not facts.force_tags


def test_tag_messages():
    facts = one('git tag -a v1 -m "Release notes"')
    assert facts.kind == "git-tag" and facts.texts == ["Release notes"]


def test_gh_posting_commands():
    for raw in (
        "gh pr create --title t --body-file /tmp/b.md",
        "gh pr merge 12 --squash --body-file x",
        "gh pr comment 3 --body hi",
        "gh issue create -t t -b b",
        "gh release create v1 --notes n",
        "gh api -X POST repos/x/y/issues/1/comments -f body=hi",
        "gh api repos/x/y/labels --input payload.json",
        "gh label create needs-triage",
        "gh workflow run ci.yml",
        "gh repo edit --description d",
    ):
        facts = one(raw)
        assert facts.post, raw


def test_gh_reads_are_not_posts():
    for raw in (
        "gh pr view 12",
        "gh pr list",
        "gh api repos/x/y",
        "gh run list",
        "gh release view v1",
        "gh pr checkout 4",
    ):
        assert not one(raw).post, raw


def test_gh_text_extraction():
    facts = one('gh pr create --title "Title here" --body "Body text" -F /tmp/extra.md')
    assert facts.texts == ["Title here", "Body text"] and facts.text_files == ["/tmp/extra.md"]
    facts = one("gh api -X POST repos/x/y/issues -f title=hello -f body='the body'")
    assert facts.texts == ["hello", "the body"]
    facts = one("gh pr merge 1 --body-file -")
    assert facts.text_from_stdin


def test_glab_posting_commands():
    assert one('glab mr create -t t -d "desc"').post
    assert one("glab issue note 4 -m hi").post
    assert not one("glab mr view 4").post


def test_chained_and_wrapped_commands(repo: Path):
    parsed = command_mod.parse('cd /x && GIT_EDITOR=true git commit -m "y" ; git push', repo)
    kinds = [c.kind for c in parsed.commands]
    assert kinds == ["other", "git-commit", "git-push"]
    assert parsed.gated


def test_reading_commands_are_not_gated():
    parsed = command_mod.parse("git log --format=%B | grep -ci 'claude\\|anthropic'")
    assert not parsed.gated
    assert command_mod.carried_text(parsed, None) == ""


def test_stdin_message_uses_raw_command():
    raw = 'printf "x\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>" | git commit -F -'
    parsed = command_mod.parse(raw)
    assert parsed.commands[-1].text_from_stdin
    assert "Co-Authored-By" in command_mod.carried_text(parsed, None)


def test_heredoc_bodies_are_captured():
    raw = "git commit -F - <<'EOF'\nSubject\n\nCo-Authored-By: Copilot <copilot@github.com>\nEOF\n"
    parsed = command_mod.parse(raw)
    assert len(parsed.heredocs) == 1
    assert "Copilot" in parsed.heredocs[0]
    assert parsed.commands[0].is_commit
    assert "Copilot" in command_mod.carried_text(parsed, None)


def test_message_file_is_read(tmp_path: Path):
    message = tmp_path / "msg.txt"
    message.write_text("Subject\n\nGenerated by ChatGPT\n", encoding="utf-8")
    parsed = command_mod.parse("git commit -F msg.txt", tmp_path)
    assert "ChatGPT" in command_mod.carried_text(parsed, tmp_path)


def test_unbalanced_quotes_do_not_crash():
    parsed = command_mod.parse('git commit -m "unterminated')
    assert parsed.commands[0].is_commit


def test_extra_posting_patterns():
    parsed = command_mod.parse(
        "curl -X POST https://hooks.example/notify", extra_posting=[r"^curl .*-X POST"]
    )
    assert parsed.commands[0].post
