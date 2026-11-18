/** Permission helpers mirror the web app so screens gate the same way. */
export function hasPermission(permissions: string[] | undefined, key: string): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(key));
}
