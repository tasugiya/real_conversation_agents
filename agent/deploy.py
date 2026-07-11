"""Deploy the conversation agent to Vertex AI Agent Engine (Inline Source Deployment).

Usage:
    python deploy.py --project-id PROJECT --region REGION \\
        --service-account agent-engine-sa-dev@PROJECT.iam.gserviceaccount.com \\
        --display-name real-conv-agent-dev \\
        --staging-bucket gs://PROJECT-agent-staging-dev

Automatically creates a new Agent Engine on the first run for a given
--display-name, or updates the existing one (found by looking up that same
display_name) on every subsequent run. The caller does not need to track or
pass a resource_name itself -- this avoids needing CI to persist state
between runs.

Called from .github/workflows/cd.yml's deploy-agent job. Agent Engine's
underlying "reasoningEngine" resource itself is intentionally NOT managed by
Terraform (docs/infra/04_DEPLOY.md §5.3) -- only its supporting IAM is.

After the very first deploy for an environment, copy the printed
resource_name into that environment's terraform.tfvars
(agent_engine_resource_name) and re-apply, so the API's
AGENT_ENGINE_RESOURCE_NAME env var points at it too.
"""

import argparse

import vertexai
from vertexai import agent_engines
from vertexai.preview import reasoning_engines

from src.agent import root_agent

REQUIREMENTS = ["google-cloud-aiplatform[agent_engines,adk]"]


def build_app() -> reasoning_engines.AdkApp:
    return reasoning_engines.AdkApp(agent=root_agent, enable_tracing=True)


def find_existing_resource_name(display_name: str) -> str | None:
    matches = list(agent_engines.list(filter=f'display_name="{display_name}"'))
    if not matches:
        return None
    if len(matches) > 1:
        raise SystemExit(
            f"Multiple Agent Engines found with display_name={display_name!r}; "
            "resolve manually (delete the extras) before deploying."
        )
    return matches[0].resource_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--staging-bucket",
        required=True,
        help="gs://... bucket for build artifacts. Required by agent_engines.create()/"
        "update() even with Inline Source Deployment.",
        # NOTE: the SA passed via --service-account (and the CI identity
        # running this script) needs roles/storage.admin on this bucket, not
        # just roles/storage.objectAdmin -- create()/update() calls
        # storage_client.get_bucket(), which requires storage.buckets.get.
    )
    args = parser.parse_args()

    vertexai.init(
        project=args.project_id,
        location=args.region,
        staging_bucket=args.staging_bucket,
    )

    app = build_app()
    existing_resource_name = find_existing_resource_name(args.display_name)

    if existing_resource_name is None:
        resource = agent_engines.create(
            agent_engine=app,
            requirements=REQUIREMENTS,
            display_name=args.display_name,
            service_account=args.service_account,
        )
        print(f"created: {resource.resource_name}")
    else:
        resource = agent_engines.update(
            resource_name=existing_resource_name,
            agent_engine=app,
            requirements=REQUIREMENTS,
            service_account=args.service_account,
        )
        print(f"updated: {resource.resource_name}")

    # Parsed by cd.yml's deploy-agent job to surface the value in the run summary.
    print(f"AGENT_ENGINE_RESOURCE_NAME={resource.resource_name}")


if __name__ == "__main__":
    main()
