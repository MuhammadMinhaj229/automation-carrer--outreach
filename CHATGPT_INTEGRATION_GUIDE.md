# ACIOS Local MCP Integration Guide

This guide applies to the local-first ACIOS CLI and STDIO MCP server. The former hosted Next.js gateway, FastAPI deployment, MongoDB/Redis production stack and web cockpit are not part of the default local workflow.

## Supported runtime

Run these commands from the repository root after installing the core requirements:

```bash
python -m acios.cli --help
python -m acios.mcp_server
```

For an MCP client that can launch a local STDIO process, configure it to run `python -m acios.mcp_server`. The client must start the process with the repository root available on `PYTHONPATH` or as its working directory. If the client cannot set a working directory, use the actual absolute repository path in its local configuration. Do not commit machine-specific paths.

The repository provides `mcp_config.example.json` as a portable starting point; adapt the local path for the specific MCP client and operating system.

## Local-only boundaries

- The STDIO MCP server is intended for a trusted local client. Do not expose it to the public internet.
- The server reads/writes the local ACIOS database and can call configured search/crawl providers. Enable only providers you understand and need.
- Draft validation is not approval. A draft is only approved through the local human review workflow.
- Programmatic send tools are retained only for compatibility and return a disabled status. ACIOS stages reviewable messages; the user sends manually from the mail client.
- Never paste API keys, OAuth refresh tokens, Gmail App Passwords or browser storage state into chat or commit them to Git.
- Use the OS credential store for persistent secrets where possible. Keep `.env`, `config/candidate_profile.yaml`, resumes and local data out of version control.

## ChatGPT hosted connectors

A local STDIO server is not the same as a hosted remote MCP endpoint. A hosted ChatGPT connector generally needs a reachable remote endpoint and supported authentication. This local-first guide does not instruct you to expose the local computer to the internet or to bypass the authentication model with a tunnel. Keep the local MCP workflow in a client that can launch local processes unless a separately reviewed, authenticated remote adapter is intentionally implemented.

## Troubleshooting

1. Run `python -m acios.cli --help` from the repository root.
2. Verify the MCP client is invoking the intended Python interpreter/virtual environment.
3. Set the local repository path for `PYTHONPATH` if the client starts with a different current directory.
4. Inspect the MCP client process log for import errors. Do not print secret environment values during troubleshooting.
5. Run the deterministic test suite before enabling additional providers.
