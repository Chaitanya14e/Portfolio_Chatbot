import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'portfolio-chat-conversations'
const API_BASE_URL = (
  import.meta.env.API_BASE_URL || 'https://portfolio-chatbot-api-ngeh.onrender.com'
).replace(/\/$/, '')
const suggestions = [
  { icon: 'user', label: 'Who are you?', prompt: 'Tell me about yourself.' },
  { icon: 'code', label: 'Explore projects', prompt: 'What projects have you worked on?' },
  { icon: 'briefcase', label: 'Work experience', prompt: 'Tell me about your experience.' },
  { icon: 'sparkles', label: 'Your skills', prompt: 'What are your key skills?' },
]

function Icon({ name, size = 18, className = '' }) {
  const paths = {
    add: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    arrow: <><path d="M7 17 17 7" /><path d="M7 7h10v10" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="14" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
    chat: <><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    close: <><path d="m18 6-12 12" /><path d="m6 6 12 12" /></>,
    code: <><path d="m16 18 6-6-6-6M8 6l-6 6 6 6M14 4l-4 16" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    sparkles: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3ZM19 14l1.1 2.9L23 18l-2.9 1.1L19 22l-1.1-2.9L15 18l2.9-1.1L19 14Z" /></>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
    trash: <><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6" /></>,
    user: <><circle cx="12" cy="8" r="5" /><path d="M20 21a8 8 0 0 0-16 0" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {paths[name]}
    </svg>
  )
}

function readConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (!Array.isArray(saved)) return []

    return saved.map((conversation) => {
      const firstUserMessage = Array.isArray(conversation.messages)
        ? conversation.messages.find((message) => message.role === 'user')
        : null
      return typeof firstUserMessage?.content === 'string'
        ? { ...conversation, title: getConversationTitle(firstUserMessage.content) }
        : conversation
    })
  } catch (error) {
    console.error('Could not load saved conversations.', error)
    return []
  }
}

function makeId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function getTimestamp() {
  return new Date().toISOString()
}

function getConversationTitle(message) {
  const normalized = message.toLowerCase()
  const topics = [
    [/\b(yourself|about you|who are you|introduce yourself|your background)\b/, 'About me'],
    [/\b(project|built|portfolio work)\b/, 'Projects'],
    [/\b(experience|career|job|work history)\b/, 'Experience'],
    [/\b(skill|technology|tech stack|programming language)\b/, 'Skills'],
    [/\b(education|study|degree|school|university)\b/, 'Education'],
    [/\b(contact|email|reach you)\b/, 'Contact'],
    [/\b(achievement|award|recognition)\b/, 'Achievements'],
  ]

  const match = topics.find(([pattern]) => pattern.test(normalized))
  if (match) return match[1]

  const ignoredWords = new Set([
    'a', 'about', 'and', 'can', 'could', 'do', 'does', 'explain', 'give',
    'help', 'how', 'i', 'is', 'me', 'my', 'of', 'please', 'tell', 'the',
    'this', 'to', 'what', 'when', 'where', 'who', 'why', 'would', 'you',
    'your',
  ])
  const topic = normalized
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter((word) => word && !ignoredWords.has(word))
    .slice(0, 3)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')

  return topic || 'Portfolio question'
}

function parseProjectCard(block) {
  const fields = Object.fromEntries(
    block.split(/\r?\n/)
      .map((line) => {
        const separator = line.indexOf(':')
        return separator === -1
          ? null
          : [line.slice(0, separator).trim().toLowerCase(), line.slice(separator + 1).trim()]
      })
      .filter(Boolean),
  )
  const safeUrl = (value) => {
    try {
      const url = new URL(value)
      return ['http:', 'https:'].includes(url.protocol) ? url.href : null
    } catch {
      return null
    }
  }

  if (!fields.name) return null

  return {
    name: fields.name,
    description: fields.description,
    technologies: fields.technologies,
    category: fields.category,
    github: safeUrl(fields.github),
    demo: safeUrl(fields.demo),
  }
}

const projectCategories = [
  'AI projects',
  'Full-stack projects',
  'Frontend projects',
  'Other projects',
]

function AssistantContent({ content }) {
  const cardPattern = /<project-card>\s*([\s\S]*?)\s*<\/project-card>/gi
  const cards = [...content.matchAll(cardPattern)]
    .map((match) => parseProjectCard(match[1]))
    .filter(Boolean)
  const remainder = content.replace(cardPattern, '')
  const partialCard = remainder.match(/<project-card>\s*([\s\S]*)$/i)
  const text = remainder.replace(/<project-card>[\s\S]*$/i, '').trim()
  const preview = partialCard ? parseProjectCard(partialCard[1]) : null
  const projects = [...cards, ...(preview ? [preview] : [])]
  const groupedProjects = projectCategories
    .map((category) => ({
      category,
      projects: projects.filter((project) => (
        projectCategories.includes(project.category) ? project.category : 'Other projects'
      ) === category),
    }))
    .filter((group) => group.projects.length)

  return (
    <>
      {text && <p className="mt-0.5 mb-0 whitespace-pre-wrap">{text}</p>}
      {groupedProjects.map((group) => (
        <section className="mt-4" key={group.category}>
          <h2 className="mb-2 text-[11px] font-semibold tracking-wide text-[#77747a] uppercase">{group.category}</h2>
          {group.projects.map((project, index) => <ProjectCard project={project} key={`${project.name}-${index}`} />)}
        </section>
      ))}
      {partialCard && !preview && <p className="mt-0.5 mb-0 whitespace-pre-wrap">{partialCard[1]}</p>}
    </>
  )
}

function ProjectCard({ project }) {
  return (
    <section className="my-3 rounded-xl border border-[#e8e2da] bg-white p-4 shadow-[0_4px_16px_rgba(48,39,30,0.04)]">
      <h3 className="m-0 text-sm font-semibold text-[#393a40]">{project.name}</h3>
      {project.description && <p className="mt-2 mb-0 whitespace-pre-wrap text-[#62616a]">{project.description}</p>}
      {project.technologies && <p className="mt-2 mb-0 text-[10px] text-[#77747a]"><strong>Technologies:</strong> {project.technologies}</p>}
      {(project.github || project.demo) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {project.github && <a className="rounded-md bg-[#f4f0eb] px-3 py-1.5 text-[10px] font-medium text-[#6b4d35] no-underline hover:bg-[#ece3d9]" href={project.github} target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a>}
          {project.demo && <a className="rounded-md bg-[#f4f0eb] px-3 py-1.5 text-[10px] font-medium text-[#6b4d35] no-underline hover:bg-[#ece3d9]" href={project.demo} target="_blank" rel="noreferrer">Live demo <span aria-hidden="true">↗</span></a>}
        </div>
      )}
    </section>
  )
}

function formatDate(value) {
  const date = new Date(value)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function App() {
  const [conversations, setConversations] = useState(readConversations)
  const [activeId, setActiveId] = useState(() => readConversations()[0]?.id || null)
  const [input, setInput] = useState('')
  const [sendingId, setSendingId] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [storageError, setStorageError] = useState(false)
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)
  const abortRef = useRef(null)
  const storageErrorRef = useRef(false)

  const activeConversation = conversations.find((conversation) => conversation.id === activeId)
  const isSending = sendingId !== null

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
      if (storageErrorRef.current) {
        storageErrorRef.current = false
        window.setTimeout(() => setStorageError(false), 0)
      }
    } catch (error) {
      console.error('Could not save conversations in this browser.', error)
      if (!storageErrorRef.current) {
        storageErrorRef.current = true
        setStorageError(true)
      }
    }
  }, [conversations])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [activeConversation?.messages])

  useEffect(() => () => abortRef.current?.abort(), [])

  function createConversation() {
    setActiveId(null)
    setInput('')
    setSidebarOpen(false)
    textareaRef.current?.focus()
  }

  function selectConversation(id) {
    setActiveId(id)
    setSidebarOpen(false)
  }

  function deleteConversation(event, id) {
    event.stopPropagation()
    setConversations((current) => current.filter((conversation) => conversation.id !== id))
    if (activeId === id) setActiveId(null)
  }

  function updateMessage(conversationId, messageId, update) {
    setConversations((current) => current
      .map((conversation) => {
        if (conversation.id !== conversationId) return conversation
        return {
          ...conversation,
          updatedAt: new Date().toISOString(),
          messages: conversation.messages.map((message) => (
            message.id === messageId ? { ...message, ...update } : message
          )),
        }
      })
      .sort((first, second) => Date.parse(second.updatedAt) - Date.parse(first.updatedAt)))
  }

  async function sendMessage(value = input) {
    const message = value.trim()
    if (!message || isSending) return

    const conversationId = activeId || makeId()
    const userMessageId = makeId()
    const assistantMessageId = makeId()
    const now = getTimestamp()
    const conversation = conversations.find((item) => item.id === conversationId)
    const newMessages = [
      ...(conversation?.messages || []),
      { id: userMessageId, role: 'user', content: message },
      { id: assistantMessageId, role: 'assistant', content: '' },
    ]

    setConversations((current) => {
      const exists = current.some((item) => item.id === conversationId)
      const updated = current
        .map((item) => item.id === conversationId
          ? { ...item, messages: newMessages, updatedAt: now }
          : item)
        .sort((first, second) => Date.parse(second.updatedAt) - Date.parse(first.updatedAt))

      if (exists) return updated
      return [{
        id: conversationId,
        title: getConversationTitle(message),
        createdAt: now,
        updatedAt: now,
        messages: newMessages,
      }, ...updated]
    })
    setActiveId(conversationId)
    setInput('')
    setSidebarOpen(false)
    setSendingId(conversationId)

    const controller = new AbortController()
    abortRef.current = controller
    let streamedAnswer = ''

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/plain' },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      })

      if (!response.ok) {
        let detail = `The server returned an error (${response.status}).`
        try {
          const payload = await response.json()
          if (payload.detail) detail = payload.detail
        } catch {
          // The response may not contain JSON.
        }
        throw new Error(detail)
      }
      if (!response.body) throw new Error('Streaming is not available in this browser.')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value: chunk } = await reader.read()
        if (done) break
        streamedAnswer += decoder.decode(chunk, { stream: true })
        updateMessage(conversationId, assistantMessageId, { content: streamedAnswer })
      }

      streamedAnswer += decoder.decode()
      updateMessage(conversationId, assistantMessageId, {
        content: streamedAnswer || 'No response was returned.',
      })
    } catch (error) {
      if (error.name === 'AbortError') {
        updateMessage(conversationId, assistantMessageId, {
          content: streamedAnswer || 'Response stopped.',
        })
      } else {
        console.error('Could not get a response from the portfolio chatbot.', error)
        updateMessage(conversationId, assistantMessageId, {
          content: `I couldn't connect to the chatbot. ${error.message} Check that the backend is running and try again.`,
          isError: true,
        })
      }
    } finally {
      setSendingId(null)
      abortRef.current = null
    }
  }

  function stopResponse() {
    abortRef.current?.abort()
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  const groupedConversations = conversations.reduce((groups, conversation) => {
    const group = formatDate(conversation.updatedAt || conversation.createdAt)
    groups[group] ||= []
    groups[group].push(conversation)
    return groups
  }, {})

  return (
    <div className="flex min-h-screen w-full overflow-hidden bg-[#fbfaf8]">
      {sidebarOpen && <button className="fixed inset-0 z-[15] border-0 bg-black/30 md:hidden" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}

      <aside className={`fixed inset-y-0 left-0 z-20 flex min-h-dvh w-[min(290px,calc(100vw-48px))] shrink-0 flex-col bg-[#17191e] px-[15px] pt-[23px] pb-[15px] text-[#f2f1ef] shadow-[12px_0_40px_rgba(12,13,17,0.2)] transition-transform duration-200 md:static md:z-10 md:min-h-screen md:w-[264px] md:translate-x-0 md:shadow-none ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between px-[6px]">
          <a className="flex items-center gap-[10px] text-sm font-semibold tracking-normal text-[#f4f1ec] no-underline" href="#" onClick={(event) => { event.preventDefault(); createConversation() }}>
            <span className="grid size-[30px] place-items-center rounded-[10px] border border-[#d3b18f]/35 bg-[#b78b65]/10 text-[#d8b28e]"><Icon name="sparkles" size={19} /></span>
            <span>Portfolio Assistant</span>
          </a>
          <button className="grid size-9 place-items-center rounded-[9px] border-0 bg-transparent p-0 text-[#c3c4ca] md:hidden" aria-label="Close menu" onClick={() => setSidebarOpen(false)}>
            <Icon name="close" />
          </button>
        </div>

        <button className="mt-[34px] flex min-h-[45px] items-center gap-[10px] rounded-[9px] border border-[#393b42] bg-[#22242a] px-[11px] text-left text-xs font-medium text-[#f4f2ef] transition-colors hover:border-[#59534d] hover:bg-[#292b31]" onClick={createConversation}>
          <Icon name="add" size={19} className="text-[#cfaa88]" />
          <span>New conversation</span>
        </button>

        <div className="mx-2 mt-8 mb-3 text-[10px] font-semibold tracking-[1.2px] text-[#777a85] uppercase">Your conversations</div>
        <nav className="min-h-0 flex-1 overflow-y-auto [scrollbar-color:#45474e_transparent] [scrollbar-width:thin]" aria-label="Saved conversations">
          {Object.entries(groupedConversations).map(([group, items]) => (
            <div className="mb-5" key={group}>
              <div className="mx-2 mb-[7px] text-[10px] font-medium text-[#777a85]">{group}</div>
              {items.map((conversation) => (
                <div className="group flex items-center gap-0.5" key={conversation.id}>
                  <button
                    className={`flex min-h-[38px] min-w-0 flex-1 items-center gap-[9px] rounded-[7px] border-0 px-[9px] text-left transition-colors ${conversation.id === activeId ? 'bg-[#292b31] text-[#f1efeb]' : 'bg-transparent text-[#a8a9b0] hover:bg-[#292b31] hover:text-[#f1efeb]'}`}
                    onClick={() => selectConversation(conversation.id)}
                    title={conversation.title}
                  >
                    <Icon name="chat" size={16} className="shrink-0 text-[#858791]" />
                    <span className="flex-1 overflow-hidden text-ellipsis text-[11px] whitespace-nowrap">{conversation.title}</span>
                  </button>
                  <button
                    className="grid size-[29px] shrink-0 place-items-center rounded-[5px] border-0 bg-transparent p-0 text-[#858791] opacity-0 transition-colors group-hover:opacity-100 group-focus-within:opacity-100 hover:bg-[#3a2d2e] hover:text-[#f2a69a]"
                    type="button"
                    aria-label={`Delete ${conversation.title}`}
                    onClick={(event) => deleteConversation(event, conversation.id)}
                  >
                    <Icon name="trash" size={15} />
                  </button>
                </div>
              ))}
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="mx-2 my-[10px] text-[11px] leading-relaxed text-[#787a84]">Your conversations will appear here.</p>
          )}
        </nav>

        <div className="mt-[14px] flex min-h-[58px] items-center gap-[10px] border-t border-[#303239] px-[5px] pt-[10px]">
          <div className="grid size-8 shrink-0 place-items-center rounded-full border border-[#d2ae8f]/30 bg-[#42372f] font-serif text-[15px] text-[#e5c2a4]">P</div>
          <div className="grid min-w-0 gap-[3px]">
            <strong className="overflow-hidden text-ellipsis text-[10px] font-medium whitespace-nowrap text-[#e8e7e5]">Portfolio assistant</strong>
            <span className="text-[9px] text-[#858791]">Ask me anything</span>
          </div>
          <span className="ml-auto size-[7px] shrink-0 rounded-full bg-[#7caa8a] shadow-[0_0_0_3px_rgba(124,170,138,0.12)]" title="Ready" />
        </div>
      </aside>

      <main className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="z-[1] flex min-h-[58px] items-center justify-between border-b border-[#e8e6e2]/80 bg-[#fbfaf8]/80 px-[14px] md:min-h-16 md:px-[39px]">
          <button className="mr-2 grid size-9 shrink-0 place-items-center rounded-[9px] border-0 bg-transparent p-0 text-[#777983] transition-colors hover:bg-[#f1f0ed] md:hidden" aria-label="Open menu" onClick={() => setSidebarOpen(true)}>
            <Icon name="menu" />
          </button>
          <div className="flex min-w-0 flex-1 items-center gap-2 text-xs font-medium text-[#4a4b53]">
            <span className="overflow-hidden text-ellipsis whitespace-nowrap font-bold text-2xl">{activeConversation?.title || 'Portfolio Assistant'}</span>
            {activeConversation && <Icon name="chevron" size={15} className="shrink-0 rotate-90 text-[#a4a3a0]" />}
          </div>
        </header>

        <section className="flex min-h-0 flex-1 flex-col overflow-auto" ref={scrollRef}>
          {storageError && (
            <div className="sticky top-[10px] z-[2] mx-auto mt-[10px] w-fit max-w-[calc(100%-28px)] rounded-lg border border-[#ecd1ca] bg-[#fff7f4] px-[13px] py-[9px] text-[11px] text-[#8b4f44]" role="alert">
              Conversation history could not be saved in this browser.
            </div>
          )}

          {!activeConversation ? (
            <div className="mx-auto my-auto w-[calc(100%-32px)] px-0 pt-[17px] pb-[30px] text-center md:w-[min(620px,calc(100%-48px))] md:pt-[23px] md:pb-[43px]">
              <p className="text-2xl font-bold text-[#4a4b53]">Welcome to My Portfolio Assistant!</p>
              <p className="mx-auto mt-0 mb-[22px] max-w-[310px] text-[11px] leading-[1.8] text-[#81818a] md:mb-7 md:max-w-[425px] md:text-xs">
                Ask me about my projects, experience, skills, or anything else you’d like to know.
              </p>
              <div className="mx-auto grid max-w-[480px] grid-cols-2 gap-2 md:gap-[10px]">
                {suggestions.map((suggestion) => (
                  <button
                    className="flex min-h-12 items-center gap-2 rounded-[9px] border border-[#ebe8e3] bg-white/60 px-2 text-left text-[9px] font-medium text-[#53535a] transition-all hover:-translate-y-0.5 hover:border-[#ddc8b4] hover:bg-[#fffdfa] hover:shadow-[0_6px_16px_rgba(67,52,39,0.06)] disabled:cursor-not-allowed disabled:opacity-60 md:min-h-[52px] md:gap-[11px] md:px-3 md:text-[10px]"
                    key={suggestion.label}
                    onClick={() => sendMessage(suggestion.prompt)}
                    disabled={isSending}
                  >
                    <span className="grid size-[26px] shrink-0 place-items-center rounded-lg bg-[#f5eee7] text-[#a47d5c] md:size-[29px]"><Icon name={suggestion.icon} size={18} /></span>
                    <span>{suggestion.label}</span>
                    <Icon name="arrow" size={15} className="ml-auto text-[#aaa5a0]" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto w-[calc(100%-24px)] py-7 pb-[26px] md:w-[min(760px,calc(100%-64px))]">
              <div className="mt-1 mb-7 flex items-center justify-center gap-[7px] text-[9px] text-[#a19e99]">
                <span className="grid text-[#b18b6c]"><Icon name="sparkles" size={17} /></span>
                <span>Conversation started</span>
              </div>
              {activeConversation.messages.map((message) => (
                <article className={`mb-[26px] flex gap-[11px] ${message.role === 'user' ? 'justify-end' : ''}`} key={message.id}>
                  {message.role === 'assistant' && (
                    <div className="grid size-7 shrink-0 place-items-center rounded-[9px] border border-[#e8d9c9] bg-[#f6eee6] text-[#a67852]"><Icon name="sparkles" size={16} /></div>
                  )}
                  <div className={`min-w-0 max-w-[min(87%,620px)] text-[11px] leading-[1.8] [overflow-wrap:anywhere] md:max-w-[min(82%,620px)] md:text-xs ${message.isError ? 'text-[#9b5147]' : 'text-[#42434a]'} ${message.role === 'user' ? 'rounded-[13px] rounded-br-[3px] border border-[#e9e2d9] bg-[#f4f0eb] px-[15px] py-[11px] text-[#393a40]' : 'pt-px'}`}>
                    {message.content && (message.role === 'assistant'
                      ? <AssistantContent content={message.content} />
                      : <p className="mt-0.5 mb-0 whitespace-pre-wrap">{message.content}</p>)}
                    {message.role === 'assistant' && sendingId === activeConversation.id && (
                      <span className="inline-flex h-6 items-center gap-1 text-[11px] text-[#99989a]" aria-label="Sending response">
                        <i className="size-[5px] rounded-full bg-[#b59476]" /><i className="size-[5px] rounded-full bg-[#b59476]" /><i className="size-[5px] rounded-full bg-[#b59476]" /><span className="ml-1">Sending response</span>
                      </span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <footer className="mx-auto w-[calc(100%-24px)] pt-[14px] pb-[17px] md:w-[min(760px,calc(100%-64px))]">
          <form className="rounded-[13px] border border-[#e7e4df] bg-white pt-[11px] pr-[10px] pb-[9px] pl-[13px] shadow-[0_5px_18px_rgba(48,39,30,0.045)] transition-[border-color,box-shadow] focus-within:border-[#cfb69f] focus-within:shadow-[0_0_0_3px_rgba(166,120,82,0.08),0_5px_18px_rgba(48,39,30,0.045)] md:pt-[13px] md:pr-[13px] md:pb-[10px] md:pl-[17px]" onSubmit={(event) => { event.preventDefault(); sendMessage() }}>
            <textarea
              className="block max-h-40 min-h-[25px] w-full resize-y border-0 bg-transparent text-xs leading-relaxed text-[#292a32] outline-none placeholder:text-[#a1a0a0]"
              ref={textareaRef}
              aria-label="Message the portfolio assistant"
              placeholder="Ask anything about my portfolio..."
              rows="1"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
            />
            <div className="mt-[9px] flex justify-end">
              <button
                className={`grid size-8 shrink-0 place-items-center rounded-[9px] border-0 text-white transition-all hover:-translate-y-px hover:bg-[#454047] disabled:cursor-not-allowed disabled:bg-[#eeece9] disabled:text-[#a3a1a0] ${isSending ? 'bg-[#a67852]' : 'bg-[#25262c]'}`}
                type={isSending ? 'button' : 'submit'}
                aria-label={isSending ? 'Stop response' : 'Send message'}
                disabled={!isSending && !input.trim()}
                onClick={isSending ? stopResponse : undefined}
              >
                <Icon name={isSending ? 'stop' : 'send'} size={17} />
              </button>
            </div>
          </form>
          <p className="mt-[9px] mb-0 text-center text-[9px] text-[#a3a1a0]">AI can make mistakes. Check important information.</p>
        </footer>
      </main>
    </div>
  )
}

export default App
