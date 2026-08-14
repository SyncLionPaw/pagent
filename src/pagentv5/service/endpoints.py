from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceEndpoint:
    name: str
    implementation: str
    resource: str
    streaming: bool = False
    legacy_names: tuple[str, ...] = ()


RESOURCE_ENDPOINTS = (
    ResourceEndpoint(
        "task.create",
        "ResourceService.create_task",
        "task",
        legacy_names=("wire:reset", "desktop:reset-session"),
    ),
    ResourceEndpoint(
        "task.open",
        "ResourceService.open_task",
        "task",
        legacy_names=("wire:resume", "desktop:resume-thread"),
    ),
    ResourceEndpoint(
        "task.list",
        "ResourceService.list_tasks",
        "task",
        legacy_names=("wire:list_threads", "desktop:list-threads"),
    ),
    ResourceEndpoint(
        "task.get",
        "ResourceService.task_details",
        "task",
        legacy_names=("wire:thread_meta", "desktop:get-thread-meta"),
    ),
    ResourceEndpoint(
        "task.metadata.update",
        "ResourceService.update_task_metadata",
        "task",
    ),
    ResourceEndpoint(
        "task.delete",
        "ResourceService.delete_task",
        "task",
        legacy_names=("wire:delete_thread", "desktop:delete-thread"),
    ),
    ResourceEndpoint(
        "session.get",
        "ResourceService.session_messages",
        "session",
        legacy_names=("wire:history", "desktop:request-history"),
    ),
    ResourceEndpoint(
        "session.replace",
        "ResourceService.replace_session",
        "session",
    ),
    ResourceEndpoint(
        "session.clear",
        "ResourceService.clear_session",
        "session",
    ),
    ResourceEndpoint(
        "sandbox.status",
        "ResourceService.sandbox_status",
        "sandbox",
        legacy_names=(
            "wire:sandbox_status",
            "desktop:get-sandbox-status",
        ),
    ),
    ResourceEndpoint(
        "sandbox.tree",
        "ResourceService.sandbox_tree",
        "sandbox",
        legacy_names=("wire:sandbox_tree", "desktop:list-sandbox-tree"),
    ),
    ResourceEndpoint(
        "sandbox.file.read",
        "ResourceService.read_sandbox_file",
        "sandbox",
    ),
    ResourceEndpoint(
        "userdir.status",
        "ResourceService.userdir_status",
        "userdir",
    ),
    ResourceEndpoint(
        "userdir.tree",
        "ResourceService.userdir_tree",
        "userdir",
        legacy_names=(
            "http:/api/project-files",
            "http:/api/project-tree",
            "desktop:list-project-files",
            "desktop:list-project-tree",
        ),
    ),
    ResourceEndpoint(
        "userdir.file.read",
        "ResourceService.read_userdir_file",
        "userdir",
        legacy_names=("http:/api/artifacts/read", "desktop:read-artifact"),
    ),
    ResourceEndpoint(
        "task.capabilities",
        "ResourceService.capabilities",
        "task",
        legacy_names=("wire:capabilities", "wire:get_config"),
    ),
    ResourceEndpoint(
        "run.start",
        "ResourceService.run",
        "runtime",
        streaming=True,
        legacy_names=(
            "wire:user",
            "desktop:send-user-input",
            "http:POST /command",
        ),
    ),
    ResourceEndpoint(
        "run.cancel",
        "ResourceService.cancel_run",
        "runtime",
        legacy_names=("wire:cancel", "desktop:cancel-run"),
    ),
)


def endpoint_inventory() -> list[dict[str, object]]:
    return [
        {
            "name": endpoint.name,
            "implementation": endpoint.implementation,
            "resource": endpoint.resource,
            "streaming": endpoint.streaming,
            "legacy_names": list(endpoint.legacy_names),
        }
        for endpoint in RESOURCE_ENDPOINTS
    ]
