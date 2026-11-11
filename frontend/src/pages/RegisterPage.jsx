import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/AuthLayout'
import { useUi } from '../ui/UiProvider'

const FIELDS = [
  { name: 'last_name', label: 'Фамилия', required: true },
  { name: 'first_name', label: 'Имя', required: true },
  { name: 'patronymic', label: 'Отчество' },
  { name: 'username', label: 'Логин', required: true, autoComplete: 'username' },
  { name: 'email', label: 'Email', type: 'email', required: true, autoComplete: 'email' },
  { name: 'phone_number', label: 'Телефон', required: true, placeholder: '+375 29 000-00-00', type: 'tel', autoComplete: 'tel' },
  { name: 'password', label: 'Пароль', type: 'password', required: true, autoComplete: 'new-password' },
  {
    name: 'password_confirm',
    label: 'Повторите пароль',
    type: 'password',
    required: true,
    autoComplete: 'new-password',
  },
]

const INITIAL_FORM = Object.fromEntries(FIELDS.map((field) => [field.name, '']))

export default function RegisterPage() {
  const { register } = useAuth()
  const { notify } = useUi()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  // Ссылка друга: /register?ref=RULI-… — код подставляется сам.
  const [form, setForm] = useState(() => ({ ...INITIAL_FORM, ref: params.get('ref') || '' }))
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      const payload = Object.fromEntries(
        Object.entries(form).filter(([, value]) => value !== ''),
      )
      await register(payload)
      notify('Аккаунт создан', {
        description: 'Дальше — Рули ID: телефон, права и проверка лица. Около 5 минут.',
      })
      navigate('/verification')
    } catch (err) {
      setError(extractError(err, 'Не удалось зарегистрироваться'))
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthLayout
      title="Регистрация"
      subtitle="Минута на аккаунт. Потом — Рули ID: код из SMS, права и лицо."
      wide
    >
      <form onSubmit={handleSubmit} className="auth-form__fields">
        <div className="form-grid">
          {FIELDS.map(({ name, label, type = 'text', ...rest }) => (
            <div className="field" key={name}>
              <label htmlFor={name}>{label}</label>
              <input id={name} type={type} value={form[name]} onChange={update(name)} {...rest} />
            </div>
          ))}
        </div>

        <div className="field">
          <label htmlFor="ref">
            Код друга <small>необязательно</small>
          </label>
          <input id="ref" value={form.ref} onChange={update('ref')} placeholder="RULI-…" autoCapitalize="characters" />
          {form.ref && <span className="field__hint field__hint--ok">+150 баллов после первой поездки — тебе и другу</span>}
        </div>

        {error && <p className="error-text">{error}</p>}

        <button type="submit" className="btn btn--cta btn--lg btn--block" disabled={pending}>
          {pending ? 'Создаём аккаунт…' : 'Зарегистрироваться'}
        </button>
      </form>

      <p className="muted auth-switch">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </p>
    </AuthLayout>
  )
}
