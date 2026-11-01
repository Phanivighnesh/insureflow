import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bot, Send, Trash2, ArrowUpRight, Sparkles, AlertCircle, ShieldAlert, Cpu } from 'lucide-react'
import { api } from '../../auth/AuthContext'
import { Badge, Button, Card, CardBody, ErrorState, PageHeader, cn } from '../../components/ui'
import type { ChatResponse, RecordRef } from '../../api/types'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content?: string
  response?: ChatResponse
  timestamp: string
}

const STORAGE_KEY = 'insureflow_copilot_chat_history'

const SUGGESTED_QUESTIONS = [
  'Why was QTE-2026-000001 referred?',
  'Explain the risk profile of APP-2026-000001.',
  'Explain the premium calculation for QTE-2026-000001.',
  'Summarize the detected policy anomalies.',
  'Summarize the history of POL-2026-000001.',
  'Which applications require senior underwriting review?',
  'What is the auto-approval limit for property?',
]

function getRecordLink(ref: RecordRef): string {
  if (ref.ui_route) return ref.ui_route
  const t = ref.type.toLowerCase()
  if (t === 'quote') return `/ops/quotes/${ref.id}`
  if (t === 'policy') return `/ops/policies/${ref.id}`
  if (t === 'applicant') return `/ops/applicants/${ref.id}`
  if (t === 'exception') return `/ops/exceptions`
  return '/ops'
}

export function Copilot() {
  const [searchParams] = useSearchParams()
  const contextType = searchParams.get('type')
  const contextId = searchParams.get('id')

  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Fetch AI provider status
  const statusQuery = useQuery({
    queryKey: ['ops', 'ai', 'status'],
    queryFn: () => api.ops.ai.status(),
    refetchInterval: 30000,
  })

  // Mirror messages to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // quota or private mode fallback
    }
  }, [messages])

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, loading])

  // Pre-fill question if context params exist
  useEffect(() => {
    if (contextType && contextId) {
      if (contextType === 'quote') {
        setInput(`Why was ${contextId} referred?`)
      } else if (contextType === 'policy') {
        setInput(`Summarize the history of ${contextId}.`)
      } else if (contextType === 'applicant') {
        setInput(`Explain the risk profile of ${contextId}.`)
      } else if (contextType === 'exception') {
        setInput(`Explain exception ${contextId}.`)
      }
    }
  }, [contextType, contextId])

  const handleSend = async (questionText?: string) => {
    const q = (questionText ?? input).trim()
    if (!q || loading) return

    setError(null)
    const userMsg: Message = {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const nextHistory = [...messages, userMsg]
    setMessages(nextHistory)
    setInput('')
    setLoading(true)

    // Build context record if provided in URL or current input
    const contextRecord = contextType && contextId ? { type: contextType, id: contextId } : undefined

    // Build history for backend (max last 6 messages)
    const historyPayload = nextHistory
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-6)
      .map((m) => ({
        role: m.role,
        content: m.role === 'user' ? (m.content ?? '') : (m.response?.summary ?? ''),
      }))

    try {
      const resp = await api.ops.ai.chat({
        question: q,
        context_record: contextRecord,
        history: historyPayload,
      })

      const assistantMsg: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        response: resp,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setMessages([])
    sessionStorage.removeItem(STORAGE_KEY)
    setError(null)
  }

  const aiStatus = statusQuery.data
  const isLlmMode = aiStatus?.mode === 'llm'

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <PageHeader
        title={
          <div className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-brand-600" />
            <span>Underwriting AI Copilot</span>
          </div>
        }
        subtitle="Explainable, read-only intelligence grounded in stored policy and underwriting records."
        actions={
          <div className="flex items-center gap-3">
            {/* Status indicator */}
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs shadow-sm">
              <span className={cn('h-2 w-2 rounded-full', isLlmMode ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400')} />
              {statusQuery.isLoading ? (
                <span className="text-slate-500">Checking AI service…</span>
              ) : isLlmMode ? (
                <span className="font-medium text-slate-700">
                  AI: Groq <span className="text-slate-500">({aiStatus?.model})</span>
                </span>
              ) : (
                <span className="font-medium text-amber-800">
                  Template mode <span className="text-slate-500">(deterministic engine)</span>
                </span>
              )}
            </div>
            {messages.length > 0 && (
              <Button variant="secondary" size="sm" onClick={handleClear}>
                <Trash2 className="h-4 w-4" />
                Clear conversation
              </Button>
            )}
          </div>
        }
      />

      {/* Main chat container */}
      <Card className="flex flex-1 flex-col overflow-hidden">
        {/* Messages scroll area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="rounded-full bg-brand-50 p-4 text-brand-600">
                <Sparkles className="h-8 w-8" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900">How can I assist your underwriting today?</h3>
              <p className="mt-1 max-w-md text-sm text-slate-500">
                Ask about quote referrals, risk scores, premium formulas, anomalies, or business rule limits.
              </p>

              {/* Suggested Questions */}
              <div className="mt-6 w-full max-w-2xl text-left">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Suggested Questions</div>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSend(q)}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-800 text-left"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={cn('flex flex-col', msg.role === 'user' ? 'items-end' : 'items-start')}
              >
                {msg.role === 'user' ? (
                  <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm text-white shadow-sm">
                    <p>{msg.content}</p>
                    <span className="mt-1 block text-right text-[10px] text-brand-100">{msg.timestamp}</span>
                  </div>
                ) : msg.response ? (
                  <div className="w-full max-w-3xl rounded-2xl rounded-tl-sm border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    {/* Header badge row */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <Badge tone={msg.response.used_fallback ? 'amber' : 'purple'}>
                          {msg.response.used_fallback ? 'Template Fallback' : `AI: ${msg.response.model || msg.response.provider}`}
                        </Badge>
                        <Badge tone="slate">Intent: {msg.response.intent}</Badge>
                        <Badge tone={msg.response.confidence === 'high' ? 'green' : msg.response.confidence === 'medium' ? 'amber' : 'slate'}>
                          Confidence: {msg.response.confidence}
                        </Badge>
                      </div>
                      <span className="text-xs text-slate-400">{msg.response.answer_id} • {msg.timestamp}</span>
                    </div>

                    {/* Summary */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Summary</h4>
                      <p className="mt-1 text-sm font-medium text-slate-900">{msg.response.summary}</p>
                    </div>

                    {/* Key Findings */}
                    {msg.response.key_findings.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Key Findings</h4>
                        <ul className="mt-1.5 space-y-1 text-sm text-slate-700">
                          {msg.response.key_findings.map((finding, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                              <span>{finding}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Supporting Rules */}
                    {msg.response.supporting_rules.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Supporting Rules</h4>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {msg.response.supporting_rules.map((rule) => (
                            <span
                              key={rule.rule_id}
                              title={rule.text}
                              className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs font-mono text-slate-700 border border-slate-200"
                            >
                              <Cpu className="h-3 w-3 text-slate-500" />
                              <span className="font-semibold">{rule.rule_id}</span>: {rule.text}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Explanation */}
                    {msg.response.explanation && (
                      <div className="rounded-lg bg-slate-50 p-3.5 text-sm text-slate-700 border border-slate-100">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Detailed Explanation</h4>
                        <p className="whitespace-pre-line leading-relaxed">{msg.response.explanation}</p>
                      </div>
                    )}

                    {/* Record References */}
                    {msg.response.record_references.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Referenced Records</h4>
                        <div className="mt-1.5 flex flex-wrap gap-2">
                          {msg.response.record_references.map((ref) => (
                            <Link
                              key={`${ref.type}-${ref.id}`}
                              to={getRecordLink(ref)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 transition"
                            >
                              <span>{ref.label || `${ref.type}: ${ref.id}`}</span>
                              <ArrowUpRight className="h-3 w-3" />
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommended Analyst Action */}
                    {msg.response.recommended_action && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-xs text-amber-900">
                        <span className="font-semibold">Recommended Analyst Action: </span>
                        <span>{msg.response.recommended_action}</span>
                      </div>
                    )}

                    {/* Limitations & Disclaimer */}
                    <div className="border-t border-slate-100 pt-3 text-[11px] text-slate-400 space-y-1">
                      {msg.response.limitations.length > 0 && (
                        <div className="flex items-center gap-1 text-slate-500">
                          <AlertCircle className="h-3 w-3 shrink-0" />
                          <span>{msg.response.limitations.join('; ')}</span>
                        </div>
                      )}
                      <p className="italic">{msg.response.disclaimer}</p>
                    </div>
                  </div>
                ) : null}
              </div>
            ))
          )}

          {/* Loading state */}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Bot className="h-4 w-4 animate-bounce text-brand-600" />
              <span>Analyzing records and synthesizing response…</span>
            </div>
          )}

          {/* Error display */}
          {error != null && (
            <ErrorState
              error={error}
              onRetry={() => handleSend()}
            />
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input box */}
        <div className="border-t border-slate-200 bg-slate-50 p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a quote, policy, exception, risk profile, or underwriting rules..."
              disabled={loading}
              className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50"
            />
            <Button
              type="submit"
              variant="primary"
              disabled={!input.trim() || loading}
              loading={loading}
            >
              <Send className="h-4 w-4" />
              <span>Send</span>
            </Button>
          </form>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Staff-only internal copilot. Deterministic engines decide; AI only explains.</span>
            <span>Max 20 queries/minute</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
