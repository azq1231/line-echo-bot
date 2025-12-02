export async function getUsers() {
  const res = await fetch('/api/admin/users', { credentials: 'include' })
  if (!res.ok) throw new Error('Fetch failed')
  return await res.json()
}

export async function updateUser(id, field, value) {
  const res = await fetch('/api/admin/update_user_field', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: id,
      field: field,
      value: value
    }),
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
  const res = await fetch(`/api/admin/refresh_user_profile/${id}`, { method: 'POST', credentials: 'include' })
  if (!res.ok) throw new Error('Refresh failed')
  return res.json()
}

export async function updateUserReminderSchedule(id, scheduleType) {
  const res = await fetch(`/api/admin/users/${id}/update_reminder_schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule_type: scheduleType }),
    credentials: 'include'
  })
  if (!res.ok) throw new Error('Update failed')
  return res.json()
}

export async function getUserAppointments(id) {
  const res = await fetch(`/api/admin/users/${id}/appointments`, {
    credentials: 'include'
  })
  if (!res.ok) throw new Error('Fetch appointments failed')
  return res.json()
}