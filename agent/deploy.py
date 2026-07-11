"""Deploy the conversation agent to Vertex AI Agent Engine (Inline Source Deployment).

Usage:
    python deploy.py create --project-id PROJECT --region REGION \\
        --service-account agent-engine-sa@PROJECT.iam.gserviceaccount.com \\
        --display-name real-conv-agent-dev

    python deploy.py update --project-id PROJECT --region REGION \\
        --service-account agent-engine-sa@PROJECT.iam.gserviceaccount.com \\
        --resource-name projects/.../reasoningEngines/...

Called from .github/workflows/cd.yml's deploy-agent job. Agent Engine's
underlying "reasoningEngine" resource itself is intentionally NOT managed by
Terraform (docs/infra/04_DEPLOY.md §5.3) -- only its supporting IAM is.
"""

import argparse

import vertexai
from vertexai import agent_engines
from vertexai.preview import reasoning_engines

from src.agent import root_agent

REQUIREMENTS = ["google-cloud-aiplatform[agent_engines,adk]"]


def build_app() -> reasoning_engines.AdkApp:
    return reasoning_engines.AdkApp(agent=root_agent, enable_tracing=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "update"])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--display-name", default="real-conv-agent")
    parser.add_argument(
        "--resource-name", help="required for update: projects/.../reasoningEngines/..."
    )
    args = parser.parse_args()

    vertexai.init(project=args.project_id, location=args.region)

    app = build_app()

    if args.action == "create":
        resource = agent_engines.create(
            agent_engine=app,
            requirements=REQUIREMENTS,
            display_name=args.display_name,
            service_account=args.service_account,
        )
        print(f"created: {resource.resource_name}")
    else:
        if not args.resource_name:
            raise SystemExit("--resource-name is required for update")
        resource = agent_engines.update(
            resource_name=args.resource_name,
            agent_engine=app,
            requirements=REQUIREMENTS,
            service_account=args.service_account,
        )
        print(f"updated: {resource.resource_name}")


if __name__ == "__main__":
    main()
