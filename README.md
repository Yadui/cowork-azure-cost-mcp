# Azure cost insights in Copilot Cowork (Work IQ + custom MCP connector)

This repo holds the companion code and the blog draft for **"Bringing Azure cost insights into Copilot Cowork with Work IQ and a custom MCP connector"**.

- [`blog.md`](blog.md): the post, with screenshots in [`screenshots/`](screenshots)
- [`sample/`](sample): a read-only Azure Cost Management MCP server (Python, Streamable HTTP, Entra auth) and a Copilot Cowork plugin package (manifest, skill, tool description)
- [`DEMO.md`](DEMO.md): steps to reproduce and record the demo

Before you package the plugin, replace the `<placeholders>` in `sample/plugin/manifest.json`. To build the zip, run `cd sample/plugin && zip -qrD ../azure-cost-plugin.zip manifest.json color.png outline.png skills tools`.
