import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/AuthLayout'
import { useUi } from '../ui/UiProvider'

// Аккаунты создаёт seed_demo; пароль у всех — логин + 12345.
const DEMO_ACCOUNTS = [
  ['demo', '· Допуск Плюс'],
  ['novice', '· стаж < 2 лет'],
  ['newbie', '· без проверки'],
  ['admin', '· модератор'],
]

export default function LoginPage() {
  const { login } = useAuth()
  const { notify } = useUi()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      await login(form.username, form.password)
      notify('С возвращением!')
      navigate(location.state?.from || '/')
    } catch (err) {
      setError(
        err?.response?.status === 401 ? 'Неверный логин или пароль' : extractError(err),
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthLayout title="Вход" subtitle="Войдите, чтобы бронировать автомобили">
      <form onSubmit={handleSubmit} className="auth-form__fields">
        <div className="field">
          <label htmlFor="username">Логин</label>
          <input
            id="username"
            value={form.username}
            onChange={update('username')}
            required
            autoComplete="username"
            autoFocus
          />
        </div>

        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={update('password')}
            required
            autoComplete="current-password"
          />
        </div>

        {error && <p className="error-text">{error}</p>}

        <button type="submit" className="btn btn--cta btn--lg btn--block" disabled={pending}>
          {pending ? 'Входим…' : 'Войти'}
        </button>

        <div className="auth-hint">
          <span>Демо-аккаунты для защиты:</span>
          <div className="auth-hint__accounts">
            {DEMO_ACCOUNTS.map(([username, label]) => (
              <button
                key={username}
                type="button"
                className="chip"
                onClick={() => setForm({ username, password: `${username}12345` })}
              >
                <b>{username}</b> {label}
              </button>
            ))}
          </div>
        </div>
      </form>

      <p className="muted auth-switch">
        Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
      </p>
    </AuthLayout>
  )
}
