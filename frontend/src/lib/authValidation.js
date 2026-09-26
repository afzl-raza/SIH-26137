// Shared client-side validation for the login/register forms. Pure
// functions - no I/O - so both forms reuse the same rules instead of each
// re-implementing them.

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Mirrors PASSWORD_MIN_LENGTH in backend/main.py - kept in sync manually
// since the frontend validates client-side before the backend gets a chance
// to reject a too-short password itself.
export const PASSWORD_MIN_LENGTH = 8;

export function validateEmail(value) {
  const trimmed = (value || '').trim();
  if (!trimmed) return 'Email is required.';
  if (!EMAIL_PATTERN.test(trimmed)) return 'Enter a valid email address.';
  return null;
}

export function validatePassword(value) {
  if (!value) return 'Password is required.';
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  return null;
}

export function validateRequired(value, label) {
  if (!value || !value.trim()) return `${label} is required.`;
  return null;
}

export function validateConfirmPassword(password, confirmPassword) {
  if (!confirmPassword) return 'Please confirm your password.';
  if (confirmPassword !== password) return 'Passwords do not match.';
  return null;
}
