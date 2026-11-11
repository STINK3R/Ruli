import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorCode, extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import CameraModal from '../camera/CameraModal'
import LivenessCheck from '../camera/LivenessCheck'
import PhoneVerify from '../components/PhoneVerify'
import { ClassAccess, LevelLadder, TripsProgress } from '../components/RuliId'
import {
  IconAlert,
  IconCamera,
  IconCheck,
  IconDocument,
  IconFace,
  IconLock,
  IconPhone,
  IconShield,
  IconSpark,
} from '../components/icons'
import {
  fetchDemoProfile,
  fetchDocumentPreview,
  startLiveness,
  submitLiveness,
  useSaveVerification,
  useStartVerification,
  useSubmitVerification,
  useUploadDocument,
  useVerification,
  useWithdrawConsent,
} from '../hooks/useVerification'
import { useQueryClient } from '@tanstack/react-query'
import { useUi } from '../ui/UiProvider'
import { DOCUMENT_KINDS, makeDemoDocument } from '../utils/demoDocuments'
import { parsePersonalNumber } from '../utils/personalNumber'
import { plural } from '../utils/plural'

// Порядок как у настоящих KYC-сервисов: телефон → данные → согласия → документы → лицо.
const STEPS = [
  ['phone', 'Телефон', IconPhone],
  ['data', 'Анкета', IconDocument],
  ['consent', 'Согласия', IconShield],
  ['documents', 'Документы', IconCamera],
  ['liveness', 'Лицо', IconFace],
]

const DOCUMENT_TYPES = [
  ['passport_by', 'Паспорт РБ'],
  ['id_card_by', 'ID-карта РБ'],
  ['foreign_passport', 'Иностранный паспорт'],
]
const BY_DOCUMENTS = ['passport_by', 'id_card_by']

const COUNTRIES = [
  ['BY', 'Беларусь'],
  ['RU', 'Россия'],
  ['KZ', 'Казахстан'],
  ['OT', 'Другая страна'],
]

const FIELDS = ['document_type', 'full_name_on_document', 'date_of_birth', 'personal_number', 'license_country',
  'license_number', 'license_issued_on', 'license_expires_on', 'category_b_since']
const DATE_FIELDS = new Set(['date_of_birth', 'license_issued_on', 'license_expires_on', 'category_b_since'])
const FRAMES = { license_front: 'card', license_back: 'card', passport_main: 'page', selfie_with_license: 'face' }

// С 23.03.2024 права в РБ выдаются на 20 лет, раньше — на 10.
const LONG_LICENSE_SINCE = '2024-03-23'

function addYears(value, years) {
  const [y, m, d] = value.split('-').map(Number)
  return `${y + years}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const formatDateTime = (value) =>
  value
    ? new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
    : ''
const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) : ''

function Stepper({ step, onStep, done }) {
  return (
    <ol className="stepper">
      {STEPS.map(([key, label, Icon], index) => (
        <li key={key} className={`${step === key ? 'is-current' : ''} ${done[key] ? 'is-done' : ''}`}>
          <button type="button" onClick={() => onStep(key)}>
            <span>{done[key] ? <IconCheck width={13} height={13} strokeWidth={3} /> : <Icon width={14} height={14} />}</span>
            <em>{index + 1}</em>
            {label}
          </button>
        </li>
      ))}
    </ol>
  )
}

function StepIntro({ icon: Icon, title, children }) {
  return (
    <div className="step-intro">
      <span className="step-intro__icon"><Icon width={22} height={22} /></span>
      <div>
        <h3>{title}</h3>
        <p className="muted">{children}</p>
      </div>
    </div>
  )
}

function DataStep({ verification, demoMode, onNext }) {
  const save = useSaveVerification()
  const { notify } = useUi()
  const [form, setForm] = useState(() =>
    Object.fromEntries(FIELDS.map((name) => [name, verification[name] || ''])),
  )
  const [filling, setFilling] = useState(false)
  const byDocument = BY_DOCUMENTS.includes(form.document_type)
  const personal = parsePersonalNumber(form.personal_number)
  const birthMismatch = personal.ok && form.date_of_birth && personal.birth !== form.date_of_birth

  const set = (name) => (event) => {
    const value = event.target.value
    setForm((current) => {
      const next = { ...current, [name]: value }
      // Подсказываем срок действия белорусских прав по дате выдачи.
      if (name === 'license_issued_on' && value && current.license_country === 'BY' && !current.license_expires_on) {
        next.license_expires_on = addYears(value, value >= LONG_LICENSE_SINCE ? 20 : 10)
      }
      if (name === 'license_issued_on' && value && !current.category_b_since) next.category_b_since = value
      // Дата рождения зашита в личный номер — подставим её, если поле пустое.
      if (name === 'personal_number') {
        const parsed = parsePersonalNumber(value)
        if (parsed.ok && !current.date_of_birth) next.date_of_birth = parsed.birth
      }
      return next
    })
  }

  const fillDemo = async () => {
    setFilling(true)
    try {
      const persona = await fetchDemoProfile()
      setForm(Object.fromEntries(FIELDS.map((name) => [name, persona[name] || ''])))
      notify('Демо-данные подставлены', {
        description: 'Запись с этими правами есть в имитации реестра ГАИ.',
        tone: 'info',
      })
    } catch (error) {
      notify('Не получилось', { description: extractError(error), tone: 'error' })
    } finally {
      setFilling(false)
    }
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(
      Object.entries(form).map(([name, value]) => [name, value === '' && DATE_FIELDS.has(name) ? null : value]),
    )
    save.mutate(payload, { onSuccess: onNext })
  }

  return (
    <form className="verify-form" onSubmit={handleSubmit}>
      <StepIntro icon={IconDocument} title="Данные как в документах">
        Поля подписаны так же, как в удостоверении. Номер прав сверим с реестром ГАИ, личный номер — по
        контрольной цифре.
      </StepIntro>
      {demoMode && (
        <button type="button" className="btn btn--soft demo-fill" disabled={filling} onClick={fillDemo}>
          <IconSpark width={16} height={16} />
          {filling ? 'Подставляем…' : 'Заполнить демо-данными для защиты'}
        </button>
      )}

      <div className="field-row">
        <div className="field">
          <label htmlFor="v-doc">Документ личности</label>
          <select id="v-doc" value={form.document_type} onChange={set('document_type')}>
            {DOCUMENT_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="v-name">ФИО как в правах</label>
          <input id="v-name" value={form.full_name_on_document} onChange={set('full_name_on_document')} required />
        </div>
      </div>

      <div className="field-row">
        {byDocument && (
          <div className="field">
            <label htmlFor="v-pn">
              Личный номер <small>14 знаков</small>
            </label>
            <input
              id="v-pn"
              value={form.personal_number}
              onChange={set('personal_number')}
              placeholder="3150589A001PB1"
              maxLength={16}
              autoCapitalize="characters"
              className="num"
              required
            />
            {personal.message && (
              <span className={`field__hint ${personal.ok ? 'field__hint--ok' : 'field__hint--bad'}`}>
                {personal.ok && <IconCheck width={12} height={12} strokeWidth={3} />} {personal.message}
              </span>
            )}
          </div>
        )}
        <div className="field">
          <label htmlFor="v-dob">Дата рождения</label>
          <input id="v-dob" type="date" value={form.date_of_birth} onChange={set('date_of_birth')} required />
          {birthMismatch && <span className="field__hint field__hint--bad">Не совпадает с датой в личном номере</span>}
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="v-country">Страна выдачи прав</label>
          <select id="v-country" value={form.license_country} onChange={set('license_country')}>
            {COUNTRIES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="v-number">
            Номер прав <small>поле 5</small>
          </label>
          <input
            id="v-number"
            className="num"
            value={form.license_number}
            onChange={set('license_number')}
            placeholder="5AB 123456"
            required
          />
        </div>
      </div>

      <div className="field-row field-row--3">
        <div className="field">
          <label htmlFor="v-issued">
            Выданы <small>4a</small>
          </label>
          <input id="v-issued" type="date" value={form.license_issued_on} onChange={set('license_issued_on')} required />
        </div>
        <div className="field">
          <label htmlFor="v-expires">
            Действуют до <small>4b</small>
          </label>
          <input id="v-expires" type="date" value={form.license_expires_on} onChange={set('license_expires_on')} required />
        </div>
        <div className="field">
          <label htmlFor="v-b">
            Категория B <small>оборот, 10</small>
          </label>
          <input id="v-b" type="date" value={form.category_b_since} onChange={set('category_b_since')} required />
        </div>
      </div>
      <p className="fine-print">Стаж считается от даты открытия категории B — по нему открываются бизнес и премиум.</p>

      {save.error && <p className="error-text">{extractError(save.error)}</p>}
      <button className="btn btn--cta btn--lg" disabled={save.isPending || (byDocument && !personal.ok)}>
        {save.isPending ? 'Сохраняем…' : 'Дальше — согласия'}
      </button>
    </form>
  )
}

/** Согласия — до фото: документы и селфи нельзя загружать без согласия на обработку (Закон № 99-З). */
function ConsentStep({ verification, consentVersion, onNext }) {
  const save = useSaveVerification()
  const consent = Boolean(verification.consent_given_at)
  const biometric = Boolean(verification.biometric_consent_at)
  const hasDocuments = verification.documents.length > 0

  return (
    <div className="verify-consent">
      <StepIntro icon={IconShield} title="Два согласия по закону">
        Без них сервер не примет ни одного фото — так требует Закон РБ № 99-З «О защите персональных данных».
      </StepIntro>
      <label className="consent">
        <input
          type="checkbox"
          checked={consent}
          disabled={save.isPending}
          onChange={(event) => save.mutate({ consent: event.target.checked })}
        />
        <span>
          <b>Обработка персональных данных</b>
          ФИО, дата рождения, личный номер, данные прав и паспорта — для проверки права управления, сверки с реестром
          ГАИ и допуска к классам автомобилей. Редакция {consentVersion}.
        </span>
      </label>
      <label className="consent">
        <input
          type="checkbox"
          checked={biometric}
          disabled={save.isPending}
          onChange={(event) => save.mutate({ biometric_consent: event.target.checked })}
        />
        <span>
          <b>Фото лица и проверка «живости»</b>
          Модератор сравнивает лицо с фото в документе вручную; кадры перед поездкой подтверждают, что за рулём вы.
          Биометрические шаблоны не создаются.
        </span>
      </label>
      <p className="fine-print">
        Согласие можно отозвать в любой момент — документы и кадры удалятся сразу.
        {hasDocuments && ' Если снять галочку сейчас, уже загруженные фото тоже удалятся.'}
      </p>
      {save.error && <p className="error-text">{extractError(save.error)}</p>}
      <button type="button" className="btn btn--cta btn--lg" disabled={!consent || !biometric || save.isPending} onClick={onNext}>
        Дальше — снимаем документы
      </button>
    </div>
  )
}

function DocumentSlot({ spec, document, locked, disabledHint, onOpen }) {
  const [preview, setPreview] = useState(null)
  const stamp = document?.uploaded_at

  useEffect(() => {
    if (!stamp) {
      setPreview(null)
      return undefined
    }
    let url = null
    let cancelled = false
    fetchDocumentPreview(spec.kind)
      .then((objectUrl) => {
        url = objectUrl
        if (cancelled) URL.revokeObjectURL(objectUrl)
        else setPreview(objectUrl)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [spec.kind, stamp])

  const reshoot = document?.needs_reshoot
  const disabled = locked || Boolean(disabledHint)
  return (
    <button
      type="button"
      className={`doc-slot ${document ? 'has-file' : ''} ${reshoot ? 'is-flagged' : ''} ${disabled ? 'is-locked' : ''}`}
      disabled={disabled}
      onClick={onOpen}
    >
      <span className="doc-slot__frame">
        {preview ? <img src={preview} alt="" /> : <IconCamera width={26} height={26} />}
        {document?.is_demo && <span className="sticker sticker--pink doc-slot__demo">Демо</span>}
      </span>
      <span className="doc-slot__body">
        <span className="doc-slot__title">
          {spec.label}
          {document && !reshoot && <IconCheck width={14} height={14} strokeWidth={2.8} />}
        </span>
        <span className="doc-slot__hint">
          {reshoot ? 'Модератор просит переснять' : locked ? 'Принято — переснимать не нужно' : disabledHint || spec.hint}
        </span>
      </span>
    </button>
  )
}

function DocumentsStep({ verification, demoMode, onStep, onNext }) {
  const upload = useUploadDocument()
  const { notify } = useUi()
  const [camera, setCamera] = useState(null)
  const [demoBusy, setDemoBusy] = useState(false)
  const needsFix = verification.status === 'needs_fix'
  const consent = Boolean(verification.consent_given_at)
  const biometric = Boolean(verification.biometric_consent_at)
  const byKind = Object.fromEntries(verification.documents.map((doc) => [doc.kind, doc]))
  const isLocked = (kind) => needsFix && byKind[kind] && !byKind[kind].needs_reshoot
  const missing = DOCUMENT_KINDS.filter(({ kind }) => !byKind[kind] || byKind[kind].needs_reshoot)

  const consentHint = (kind) => {
    if (!consent) return 'Сначала дайте согласие на обработку данных'
    if (kind === 'selfie_with_license' && !biometric) return 'Нужно согласие на фото лица'
    return null
  }

  const send = (kind, file, demo = false) =>
    upload.mutateAsync({ kind, file, demo }).then(
      () => setCamera(null),
      (error) => {
        if (errorCode(error) === 'consent_required') onStep('consent')
        notify('Фото не принято', { description: extractError(error), tone: 'error' })
      },
    )

  const fillDemo = async () => {
    setDemoBusy(true)
    try {
      for (const { kind } of missing) {
        if (!isLocked(kind)) await upload.mutateAsync({ kind, file: await makeDemoDocument(kind, verification), demo: true })
      }
    } catch (error) {
      notify('Фото не принято', { description: extractError(error), tone: 'error' })
    } finally {
      setDemoBusy(false)
    }
  }

  return (
    <div className="verify-docs">
      <StepIntro icon={IconCamera} title="Снимите 4 документа камерой">
        Только живая съёмка в приложении — из галереи загрузить нельзя. Так в заявку не попадут старые, чужие или
        отредактированные фото.
      </StepIntro>
      <div className="doc-grid">
        {DOCUMENT_KINDS.map((spec) => (
          <DocumentSlot
            key={spec.kind}
            spec={spec}
            document={byKind[spec.kind]}
            locked={isLocked(spec.kind)}
            disabledHint={consentHint(spec.kind)}
            onOpen={() => setCamera(spec)}
          />
        ))}
      </div>

      <div className="privacy-note">
        <IconShield width={18} height={18} />
        <p>
          Фото хранятся в закрытом хранилище и открываются только модератору — каждый просмотр пишется в журнал.
          Метаданные (геолокация, модель телефона) удаляются. После решения файлы удаляются через 30 дней.
        </p>
      </div>

      <div className="verify-actions">
        {demoMode && (
          <button type="button" className="btn btn--soft" onClick={fillDemo} disabled={demoBusy || !missing.length || !consent || !biometric}>
            <IconSpark width={16} height={16} />
            {demoBusy ? 'Рисуем документы…' : 'Демо-документы'}
          </button>
        )}
        <button type="button" className="btn btn--cta btn--lg" disabled={missing.length > 0} onClick={onNext}>
          {missing.length ? `Осталось снять: ${missing.length}` : 'Дальше — проверка лица'}
        </button>
      </div>

      {camera && (
        <CameraModal
          title={camera.label}
          hint={camera.hint}
          frame={FRAMES[camera.kind]}
          busy={upload.isPending}
          onClose={() => setCamera(null)}
          onCapture={(blob) => send(camera.kind, blob)}
          onDemo={demoMode ? async () => send(camera.kind, await makeDemoDocument(camera.kind, verification), true) : null}
        />
      )}
    </div>
  )
}

function LivenessStep({ verification, demoMode, onSubmitted, onStep }) {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()
  const submit = useSubmitVerification()
  const { notify } = useUi()
  const [open, setOpen] = useState(false)
  const passed = Boolean(verification.liveness_passed_at)
  const checks = submit.error?.response?.data?.checks || []

  const handleSubmit = () =>
    submit.mutate(undefined, {
      onSuccess: () => {
        notify('Заявка отправлена', { description: 'Модератор проверит документы — статус обновится сам.' })
        onSubmitted?.()
      },
    })

  return (
    <div className="verify-liveness">
      <StepIntro icon={IconFace} title="Проверка «живости»">
        Сервер выберет 3 случайных движения — повернуть голову, улыбнуться, приблизиться. Фото или видео с чужого
        экрана под случайный набор не подойдёт.
      </StepIntro>

      <div className={`liveness-card ${passed ? 'is-passed' : ''}`}>
        <span className="liveness-card__icon">{passed ? <IconCheck width={28} height={28} strokeWidth={3} /> : <IconFace width={30} height={30} />}</span>
        <div>
          <b>{passed ? 'Пройдена' : 'Ещё не пройдена'}</b>
          <small>{passed ? formatDateTime(verification.liveness_passed_at) : 'Около 10 секунд, нужна фронтальная камера'}</small>
        </div>
        <button type="button" className={`btn ${passed ? 'btn--ghost' : 'btn--cta'}`} onClick={() => setOpen(true)}>
          {passed ? 'Пройти заново' : 'Начать'}
        </button>
      </div>

      {submit.error && (
        <div className="notice notice--danger verify-errors">
          <b>{extractError(submit.error)}</b>
          {checks.length > 1 && (
            <ul>
              {checks.map((check) => (
                <li key={check.code + check.message}>
                  <button type="button" className="link-gold" onClick={() => onStep(check.step)}>
                    {check.message}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button type="button" className="btn btn--cta btn--lg btn--block" disabled={!passed || submit.isPending} onClick={handleSubmit}>
        {submit.isPending ? 'Отправляем…' : 'Отправить на проверку'}
      </button>
      <p className="fine-print">
        Перед отправкой сервер ещё раз сверит всё: телефон, личный номер, реестр ГАИ, сроки, дубликаты прав и фото.
      </p>

      {open && (
        <LivenessCheck
          demoMode={demoMode}
          start={startLiveness}
          submit={submitLiveness}
          onClose={() => setOpen(false)}
          onPassed={(payload) => {
            queryClient.setQueryData(['verification'], payload)
            refreshUser()
            setOpen(false)
          }}
        />
      )}
    </div>
  )
}

function Wizard({ payload }) {
  const { verification } = payload
  const { user } = useAuth()
  const hasAllDocs = DOCUMENT_KINDS.every(({ kind }) =>
    verification.documents.some((doc) => doc.kind === kind && !doc.needs_reshoot),
  )
  const dataDone = FIELDS.every((name) => name === 'personal_number' && !BY_DOCUMENTS.includes(verification.document_type) ? true : verification[name])
  const consentDone = Boolean(verification.consent_given_at && verification.biometric_consent_at)
  const done = {
    phone: Boolean(user?.phone_verified),
    data: dataDone,
    consent: consentDone,
    documents: hasAllDocs,
    liveness: Boolean(verification.liveness_passed_at),
  }
  const [step, setStep] = useState(() => {
    if (verification.status === 'needs_fix') return 'documents'
    return STEPS.map(([key]) => key).find((key) => !done[key]) || 'liveness'
  })

  return (
    <div className="card verify-card">
      {verification.status === 'needs_fix' && (
        <div className="notice notice--warn">
          <b>Модератор просит переснять фото.</b> {verification.rejection_text}
          {verification.reviewer_comment && <div>«{verification.reviewer_comment}»</div>}
        </div>
      )}
      <Stepper step={step} onStep={setStep} done={done} />
      <div className="verify-card__body" key={step}>
        {step === 'phone' && (
          <>
            <StepIntro icon={IconPhone} title="Телефон — первым">
              На этот номер придут коды и уведомления о поездках. Один номер — один аккаунт.
            </StepIntro>
            <PhoneVerify onDone={() => setStep(dataDone ? 'consent' : 'data')} />
            {done.phone && (
              <button type="button" className="btn btn--cta btn--lg" onClick={() => setStep('data')}>
                Дальше — анкета
              </button>
            )}
          </>
        )}
        {step === 'data' && (
          <DataStep verification={verification} demoMode={payload.demo_mode} onNext={() => setStep(consentDone ? 'documents' : 'consent')} />
        )}
        {step === 'consent' && (
          <ConsentStep verification={verification} consentVersion={payload.consent_version} onNext={() => setStep('documents')} />
        )}
        {step === 'documents' && (
          <DocumentsStep verification={verification} demoMode={payload.demo_mode} onStep={setStep} onNext={() => setStep('liveness')} />
        )}
        {step === 'liveness' && <LivenessStep verification={verification} demoMode={payload.demo_mode} onStep={setStep} />}
      </div>
    </div>
  )
}

function Intro({ payload }) {
  const start = useStartVerification()
  const { verification, access } = payload
  const rejected = verification?.status === 'rejected'
  const expired = access.status === 'expired'
  const invalid = access.status === 'license_invalid'

  return (
    <div className="card verify-card verify-intro">
      {rejected && (
        <div className="notice notice--danger">
          <b>Заявка отклонена.</b> {verification.rejection_text}
          {verification.reviewer_comment && <div>«{verification.reviewer_comment}»</div>}
        </div>
      )}
      {expired && <div className="notice notice--warn">Срок действия прав истёк — загрузите действующее удостоверение.</div>}
      {invalid && <div className="notice notice--danger">По данным ГАИ права сейчас недействительны — поездки закрыты.</div>}
      <span className="sticker sticker--pink">5 минут</span>
      <h2 className="display drip">Пройди Рули ID</h2>
      <ul className="verify-intro__list">
        <li>
          <IconPhone width={18} height={18} />
          Код из SMS — один номер на один аккаунт
        </li>
        <li>
          <IconDocument width={18} height={18} />
          Анкета: номер прав сверяется с реестром ГАИ, личный номер — по контрольной цифре
        </li>
        <li>
          <IconCamera width={18} height={18} />
          4 документа живой камерой — без загрузки из галереи
        </li>
        <li>
          <IconFace width={18} height={18} />
          Проверка «живости»: случайные движения перед камерой
        </li>
      </ul>
      {start.error && <p className="error-text">{extractError(start.error)}</p>}
      <button className="btn btn--cta btn--lg" disabled={start.isPending} onClick={() => start.mutate()}>
        {start.isPending ? 'Открываем…' : rejected || expired ? 'Подать новую заявку' : 'Начать'}
      </button>
    </div>
  )
}

function Pending({ payload }) {
  const { verification, expected_wait_minutes: wait } = payload
  const warnings = verification.user_checks.filter((check) => check.level === 'warn')
  const steps = [
    ['Заявка отправлена', formatDateTime(verification.submitted_at), 'done'],
    [
      'Автопроверки пройдены',
      warnings.length
        ? `Модератор обратит внимание: ${warnings.map((w) => w.message).join(' ')}`
        : 'Телефон, личный номер, реестр ГАИ, сроки, дубликаты',
      'done',
    ],
    ['Лицо сверяется с документами', `Обычно около ${wait} мин — статус обновится сам`, 'current'],
    ['Доступ к поездкам', 'Откроются классы по возрасту и стажу', ''],
  ]
  return (
    <div className="card verify-card">
      <span className="sticker">На проверке</span>
      <h2 className="display drip">Ждём модератора</h2>
      <ol className="timeline">
        {steps.map(([title, text, state]) => (
          <li key={title} className={`timeline__item ${state ? `is-${state}` : ''}`}>
            <span className="timeline__dot" />
            <div>
              <div className="timeline__title">{title}</div>
              <div className="timeline__text">{text}</div>
            </div>
          </li>
        ))}
      </ol>
      <p className="fine-print">Пока идёт проверка, можно выбрать машину на карте — бронь откроется сразу после одобрения.</p>
    </div>
  )
}

function Approved({ payload }) {
  const start = useStartVerification()
  const { verification, access } = payload
  return (
    <div className="card verify-card verify-approved">
      <div className="id-badge" aria-hidden="true">
        <img src="/icons/icon-192.png" alt="" />
        <span className="sticker">ID</span>
      </div>
      <div className="verify-approved__body">
        <div className="overline overline--gold">Рули ID · {access.level_display}</div>
        <h2 className="display">{verification.full_name_on_document}</h2>
        <p className="muted">
          Права действуют до {formatDate(verification.license_expires_on)}
          {access.experience_years != null && ` · стаж ${plural(access.experience_years, ['год', 'года', 'лет'])}`}
        </p>
        <div className="verify-approved__actions">
          <Link to="/" className="btn btn--cta">
            К машинам
          </Link>
          <button className="btn btn--ghost" disabled={start.isPending} onClick={() => start.mutate()}>
            Обновить права
          </button>
        </div>
        {start.error && <p className="error-text">{extractError(start.error)}</p>}
        <p className="fine-print">При обновлении прав текущий допуск действует, пока модератор проверяет новые документы.</p>
      </div>
    </div>
  )
}

function Withdraw() {
  const withdraw = useWithdrawConsent()
  const { notify } = useUi()
  const [confirming, setConfirming] = useState(false)

  if (!confirming) {
    return (
      <button type="button" className="link-danger" onClick={() => setConfirming(true)}>
        Отозвать согласие и удалить документы
      </button>
    )
  }
  return (
    <div className="notice notice--danger withdraw">
      <IconAlert width={18} height={18} />
      <div>
        <b>Удалить фото документов и кадры лица и закрыть доступ к поездкам?</b>
        <p>Для новых поездок права придётся подтвердить заново.</p>
        <div className="withdraw__actions">
          <button
            type="button"
            className="btn btn--danger"
            disabled={withdraw.isPending}
            onClick={() =>
              withdraw.mutate(undefined, {
                onSuccess: () => {
                  setConfirming(false)
                  notify('Согласие отозвано', { description: 'Документы и кадры удалены.', tone: 'info' })
                },
              })
            }
          >
            Удалить
          </button>
          <button type="button" className="btn btn--soft" onClick={() => setConfirming(false)}>
            Оставить
          </button>
        </div>
      </div>
    </div>
  )
}

export default function VerificationPage() {
  const { data: payload, isLoading, isError } = useVerification()

  if (isLoading) return <div className="skeleton" style={{ height: 420 }} />
  if (isError || !payload) return <div className="state">Не удалось загрузить статус проверки</div>

  const { verification, access } = payload
  const status = verification?.status
  let body
  if (access.status === 'blocked') {
    body = (
      <div className="card verify-card">
        <div className="notice notice--danger">
          <IconLock width={16} height={16} /> Аккаунт заблокирован — обратитесь в поддержку.
        </div>
      </div>
    )
  } else if (status === 'draft' || status === 'needs_fix') {
    body = <Wizard key={verification.id} payload={payload} />
  } else if (status === 'pending') {
    body = <Pending payload={payload} />
  } else if (status === 'approved' && !['expired', 'license_invalid'].includes(access.status)) {
    body = <Approved payload={payload} />
  } else {
    body = <Intro payload={payload} />
  }

  return (
    <div className="verify fade-up">
      <header className="page-head">
        <div className="overline">Рули ID · проверка водителя</div>
        <h1 className="display drip">Кто за рулём?</h1>
        <p className="muted">{access.next_step}</p>
      </header>

      <div className="verify-layout">
        <div className="verify-main">
          {body}
          {verification && !['revoked', 'superseded'].includes(status) && <Withdraw />}
        </div>
        <aside className="card verify-side">
          <h3>Уровни доступа</h3>
          <LevelLadder access={access} />
          <TripsProgress access={access} />
          <h3>Классы автомобилей</h3>
          <ClassAccess access={access} />
        </aside>
      </div>
    </div>
  )
}
