# JobMatch AI - Installation Package

A complete AI-powered job matching system featuring semantic search, knowledge graphs, and intelligent job recommendations.

## Docker Deployment

The repository includes local-source `Dockerfile` and Docker Compose configuration. See [Docker容器化部署说明](docs/Docker容器化部署说明.md) for the complete Chinese deployment, verification, shutdown, and troubleshooting procedure.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Open <http://localhost:18080> after all services are running.

## Features

- **Semantic Job Search**: Natural language queries with AI understanding
- **Resume Matching**: Upload resumes and get personalized job recommendations
- **Knowledge Graph**: Visualize skill relationships and job connections
- **AI-Powered Reranking**: Intelligent job scoring with detailed explanations
- **Multi-Database Architecture**: Elasticsearch for search, Neo4j for relationships

## Quick Start

### Prerequisites

Before you begin, ensure you have:

- **Docker Desktop** installed and running
  - [Download for macOS](https://docs.docker.com/desktop/install/mac-install/)
  - [Download for Windows](https://docs.docker.com/desktop/install/windows-install/)
  - [Download for Linux](https://docs.docker.com/desktop/install/linux-install/)
- **8GB+ RAM** available for Docker
- **10GB+ free disk space**
- **Internet connection** for pulling Docker images

### Installation

#### Linux / macOS

```bash
# 1. Make the installer executable
chmod +x install.sh

# 2. Run the installer
./install.sh
```

#### Windows

```powershell
# Run in PowerShell
.\install.ps1
```

For the current local source build, you can also start directly:

```powershell
docker compose up -d --build
```

### First-Time Setup

When you run the installer for the first time:

1. It will create a `.env` file from `.env.example`
2. **Optional**: Edit the `.env` file to add:
   - `ANTHROPIC_API_KEY`: For AI-powered reranking explanations (optional)

Example `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-xxx  # Optional - for AI features
```

**Note**: This package now builds backend and frontend from local source so code fixes are reflected after `docker compose up -d --build`.

### What the Installer Does

The installation script will:

1. Check that Docker is installed and running
2. Build backend and frontend from local source
3. Start all services (Elasticsearch, Neo4j, Backend, Frontend)
4. Display access URLs

Sample job data can be imported after startup:

```powershell
.\scripts\import-sample-data.ps1
```

**Installation takes 2-3 minutes** depending on your internet speed.

## Accessing the Application

After installation, access the application at:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:18080 | Main web interface |
| **Backend API** | http://localhost:18088 | REST API endpoints |
| **API Documentation** | http://localhost:18088/docs | Interactive API docs (Swagger) |
| **Elasticsearch** | http://localhost:9200 | Search engine |
| **Neo4j Browser** | http://localhost:7474 | Graph database UI |

### Neo4j Login Credentials

```
Username: neo4j
Password: password
```
**Enjoy exploring JobMatch AI!** 🚀
