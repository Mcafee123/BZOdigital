async function handleResponse(res) {
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
    }
    return res.json();
}
export async function api(path, init) {
    const res = await fetch(path, {
        ...init,
        headers: { 'Accept': 'application/json', ...(init?.headers ?? {}) },
    });
    return handleResponse(res);
}
export async function apiUpload(path, body) {
    const res = await fetch(path, { method: 'POST', body });
    return handleResponse(res);
}
