export async function getUsers() {
  const res = await fetch('/api/admin/users', { credentials: 'include' })
  if (!res.ok) throw new Error('Fetch failed')
  return await res.json()
}

export async function updateUser(id, field, value) {
  const endpoint = {
    name: '/admin/update_user_name',
    zhuyin: '/admin/update_user_zhuyin',
    phone: '/admin/update_user_phone',
    phone2: '/admin/update_user_phone',
  }[field]

  const body = { user_id: id }
  if (field === 'phone' || field === 'phone2') {
    body.phone = value
    body.field = field
  } else {
    body[field] = value
  }

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include'
  })
  if (!res.ok) throw new Error('Update failed')
  return res.json()
}

export async function addManual(name) {
  const res = await fetch('/api/admin/users/add_manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
    credentials: 'include'
  })
  if (!res.ok) throw new Error('Add failed')
  return res.json()
}

export async function mergeUsers(sourceId, targetId) {
  const res = await fetch('/api/admin/users/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_user_id: sourceId, target_user_id: targetId }),
    credentials: 'include'
  })
  if (!res.ok) throw new Error('Merge failed')
  return res.json()
}

export async function deleteUserApi(id) {
  const res = await fetch(`/api/admin/users/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) throw new Error('Delete failed')
  return res.json()
}

export async function refreshProfile(id) {
  const res = await fetch(`/admin/refresh_user_profile/${id}`, { method: 'POST', credentials: 'include' })
  if (!res.ok) throw new Error('Refresh failed')
  return res.json()
}