import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Mic, MicOff, Send, X, CheckCircle2, XCircle } from 'lucide-react'

const API = 'http://localhost:8000'

export default function QuizPanel({ question, sessionId, onClose, onResult }) {
    const [mode,    setMode]    = useState('idle')   // idle | recording | judging | done
    const [answer,  setAnswer]  = useState('')
    const [result,  setResult]  = useState(null)
    const recorderRef  = useRef(null)
    const chunksRef    = useRef([])

    const submitAnswer = useCallback(async (text) => {
        if (!text.trim()) return
        setMode('judging')
        try {
            const res = await fetch(`${API}/answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    question:   question,
                    user_answer: text,
                }),
            })
            const data = await res.json()
            setResult(data)
            if (onResult) onResult(data)
            setMode('done')
        } catch {
            setMode('idle')
        }
    }, [question, sessionId, onResult])

    const startMicAnswer = async () => {
        setMode('recording')
        chunksRef.current = []
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
        recorderRef.current = rec
        rec.ondataavailable = e => { if (e.data.size) chunksRef.current.push(e.data) }
        rec.onstop = async () => {
            stream.getTracks().forEach(t => t.stop())
            const blob   = new Blob(chunksRef.current, { type: 'audio/webm' })
            const buffer = await blob.arrayBuffer()
            const b64    = btoa(String.fromCharCode(...new Uint8Array(buffer)))
            // Use Nova Sonic to transcribe the answer audio
            setMode('judging')
            try {
                const res  = await fetch(`${API}/voice`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ audio: b64 }),
                })
                const data = await res.json()
                const spoken = data.transcript || ''
                await submitAnswer(spoken || 'I am not sure')
            } catch { setMode('idle') }
        }
        rec.start()
    }

    const stopMicAnswer = () => recorderRef.current?.stop()

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 z-50 flex items-end justify-center p-6 pb-40 pointer-events-none"
        >
            <div className="pointer-events-auto w-full max-w-xl p-7 rounded-[32px] bg-black/70 border border-cyan-500/30 backdrop-blur-[50px] shadow-[0_0_60px_rgba(6,182,212,0.15)]">
                {/* Header */}
                <div className="flex items-start justify-between mb-5">
                    <div>
                        <div className="text-[9px] uppercase text-cyan-400 font-bold tracking-widest mb-1">Nova 2 Lite · Comprehension Check</div>
                        <p className="text-base font-medium text-white/90">{question}</p>
                    </div>
                    <button onClick={onClose} className="text-white/30 hover:text-white ml-4 mt-1 flex-shrink-0">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Result */}
                {mode === 'done' && result && (
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                        className={`flex items-start gap-3 p-4 rounded-2xl mb-4 ${result.correct ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'}`}
                    >
                        {result.correct
                            ? <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                            : <XCircle      className="w-5 h-5 text-red-400      flex-shrink-0 mt-0.5" />}
                        <div>
                            <p className="text-sm text-white/80">{result.feedback}</p>
                            {result.learner && (
                                <p className="text-[10px] text-white/30 mt-2 uppercase tracking-widest">
                                    Level: {result.learner.level} · {result.learner.correct_answers} correct answers
                                </p>
                            )}
                        </div>
                    </motion.div>
                )}

                {/* Input row */}
                {mode !== 'done' && (
                    <div className="flex items-center gap-3">
                        <input
                            value={answer}
                            onChange={e => setAnswer(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && submitAnswer(answer)}
                            placeholder="Type your answer…"
                            disabled={mode === 'judging' || mode === 'recording'}
                            className="flex-1 bg-white/5 border border-white/10 rounded-full px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none disabled:opacity-40"
                        />
                        <button
                            onClick={() => submitAnswer(answer)}
                            disabled={!answer.trim() || mode !== 'idle'}
                            className="p-2.5 rounded-full bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-30 transition-all"
                        >
                            <Send className="w-4 h-4" />
                        </button>
                        <button
                            onClick={mode === 'recording' ? stopMicAnswer : startMicAnswer}
                            disabled={mode === 'judging'}
                            className={`p-2.5 rounded-full border transition-all disabled:opacity-30 ${mode === 'recording' ? 'bg-red-500 border-red-500 text-white' : 'bg-white/5 border-white/10 text-white/50 hover:text-white'}`}
                        >
                            {mode === 'recording' ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                        </button>
                    </div>
                )}

                {mode === 'judging' && (
                    <p className="text-center text-xs text-white/30 uppercase tracking-widest mt-3 animate-pulse">Nova 2 Lite judging…</p>
                )}
            </div>
        </motion.div>
    )
}
