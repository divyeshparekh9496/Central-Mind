import { useState, useEffect, useRef, useCallback } from 'react'
import SolarSystem from './components/SolarSystem'
import QuizPanel from './components/QuizPanel'
import { Mic, MicOff, Search, X, Zap, ChevronUp, Loader2, Volume2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const API = 'http://localhost:8000'

// Learner level colours
const LEVEL_COLOR = {
    beginner:     'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
    intermediate: 'text-amber-400  border-amber-400/30  bg-amber-400/10',
    expert:       'text-violet-400 border-violet-400/30 bg-violet-400/10',
}

function App() {
    const [activeTab,     setActiveTab]     = useState('chat')   // chat | learning
    const [status,        setStatus]        = useState('idle')   // idle | recording | thinking | speaking
    const [transcript,    setTranscript]    = useState('')
    const [response,      setResponse]      = useState('')
    const [checkQuestion, setCheckQuestion] = useState(null)
    const [confidence,    setConfidence]    = useState(0)
    const [sources,       setSources]       = useState([])
    const [showSources,   setShowSources]   = useState(false)
    const [learner,       setLearner]       = useState({ level: 'beginner', topics_covered: [], correct_answers: 0 })
    const [searchText,    setSearchText]    = useState('')
    const [showSearch,    setShowSearch]    = useState(false)
    const [quizOpen,      setQuizOpen]      = useState(false)

    const audioRef      = useRef(null)
    const recorderRef   = useRef(null)
    const chunksRef     = useRef([])
    const sessionId     = useRef('session_' + Math.random().toString(36).slice(2))

    // ------------------------------------------------------------------
    // Audio helpers
    // ------------------------------------------------------------------
    const stopCurrentAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause()
            audioRef.current = null
        }
    }, [])

    const playBase64Audio = useCallback((b64) => {
        stopCurrentAudio()
        const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
        const blob = new Blob([bytes], { type: 'audio/wav' })
        const url  = URL.createObjectURL(blob)
        audioRef.current = new Audio(url)
        audioRef.current.play().catch(e => console.warn('Audio:', e))
        audioRef.current.onended = () => setStatus('idle')
    }, [stopCurrentAudio])

    const playTTS = useCallback((text) => {
        stopCurrentAudio()
        audioRef.current = new Audio(`${API}/tts?text=${encodeURIComponent(text)}`)
        audioRef.current.play().catch(e => console.warn('TTS:', e))
        audioRef.current.onended = () => setStatus('idle')
    }, [stopCurrentAudio])

    // ------------------------------------------------------------------
    // Text query → Nova 2 Lite /chat
    // ------------------------------------------------------------------
    const handleQuery = useCallback(async (queryText) => {
        if (!queryText.trim()) return
        setStatus('thinking')
        setTranscript(queryText)
        stopCurrentAudio()
        try {
            const res = await fetch(`${API}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: queryText, session_id: sessionId.current }),
            })
            const data = await res.json()
            setResponse(data.response)
            setCheckQuestion(data.check_question || null)
            setConfidence(data.confidence)
            setSources(data.sources || [])
            if (data.learner) setLearner(data.learner)
            
            // Auto-switch to learning tab if voice command mentions learning
            const lowerQuery = queryText.toLowerCase()
            if (lowerQuery.includes('quiz') || lowerQuery.includes('learning') || lowerQuery.includes('academy') || lowerQuery.includes('progress')) {
                setActiveTab('learning')
            }

            setStatus('speaking')
            playTTS(data.response)
        } catch (e) {
            console.error(e)
            setResponse('Could not reach Nova 2 Lite. Is the backend running?')
            setStatus('idle')
        }
    }, [stopCurrentAudio, playTTS])

    // ------------------------------------------------------------------
    // Voice query → Nova Sonic /voice
    // ------------------------------------------------------------------
    const startRecording = async () => {
        setStatus('recording')
        setTranscript('Listening via Nova 2 Sonic…')
        stopCurrentAudio()
        chunksRef.current = []
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
            recorderRef.current = rec
            rec.ondataavailable = e => { if (e.data.size) chunksRef.current.push(e.data) }
            rec.onstop = async () => {
                stream.getTracks().forEach(t => t.stop())
                const blob   = new Blob(chunksRef.current, { type: 'audio/webm' })
                const buffer = await blob.arrayBuffer()
                const b64    = btoa(String.fromCharCode(...new Uint8Array(buffer)))
                setStatus('thinking')
                
                try {
                    // 1. Start streaming request
                    const res = await fetch(`${API}/voice_stream`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ audio: b64 }),
                    })

                    if (!res.ok) throw new Error('Streaming failed')

                    // 2. Clear UI
                    setTranscript('Nova Sonic responding...')
                    setStatus('speaking')

                    // 3. Setup MediaSource for low-latency playback
                    const mediaSource = new MediaSource()
                    const audio = new Audio()
                    audio.src = URL.createObjectURL(mediaSource)
                    audioRef.current = audio
                    
                    mediaSource.addEventListener('sourceopen', async () => {
                        const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg')
                        const reader = res.body.getReader()
                        
                        audio.play().catch(e => console.warn('Playback start:', e))

                        try {
                            let chunksReceived = 0
                            while (true) {
                                const { done, value } = await reader.read()
                                if (done) {
                                    console.log('Stream complete. Total chunks:', chunksReceived)
                                    if (chunksReceived === 0) {
                                        setResponse('Nova Sonic returned an empty stream. Please check your AWS credentials and internet connection.')
                                        setStatus('idle')
                                    }
                                    break
                                }

                                chunksReceived++
                                console.log(`Received chunk ${chunksReceived} (${value.length} bytes)`)

                                // Append chunk to buffer
                                if (sourceBuffer.updating) {
                                    await new Promise(r => sourceBuffer.addEventListener('updateend', r, { once: true }))
                                }
                                sourceBuffer.appendBuffer(value)
                            }
                            
                            // Signal end of stream
                            if (sourceBuffer.updating) {
                                sourceBuffer.addEventListener('updateend', () => {
                                    if (mediaSource.readyState === 'open') mediaSource.endOfStream()
                                }, { once: true })
                            } else {
                                if (mediaSource.readyState === 'open') mediaSource.endOfStream()
                            }
                        } catch (e) {
                            console.error('Stream read error:', e)
                            setStatus('idle')
                        }
                    })

                    audio.onplaying = () => console.log('Audio playback started')
                    audio.onended = () => {
                        console.log('Audio playback ended')
                        setStatus('idle')
                    }
                    audio.onerror = (e) => {
                        console.error('Audio element error:', e)
                        setStatus('idle')
                    }

                } catch (e) {
                    console.error(e)
                    setStatus('idle')
                }
            }
            rec.start()
        } catch (err) {
            console.error('Mic access denied:', err)
            setStatus('idle')
        }
    }

    const stopRecording = () => {
        recorderRef.current?.stop()
    }

    const toggleMic = () => {
        if (status === 'recording') {
            stopRecording()
        } else if (status === 'idle' || status === 'speaking') {
            startRecording()
        }
    }

    // ------------------------------------------------------------------
    // Search submit
    // ------------------------------------------------------------------
    const handleSearchSubmit = (e) => {
        e.preventDefault()
        if (searchText.trim()) {
            handleQuery(searchText.trim())
            setSearchText('')
            setShowSearch(false)
        }
    }

    // ------------------------------------------------------------------
    // Render
    // ------------------------------------------------------------------
    const micActive  = status === 'recording'
    const isBusy     = status === 'thinking'
    const isSpeaking = status === 'speaking'

    return (
        <div className="relative w-full h-screen overflow-hidden text-white font-sans">

            {/* 3-D Solar System — planets fire handleQuery on click */}
            <div className="absolute inset-0 z-0">
                <SolarSystem onPlanetClick={(name) => handleQuery(`Tell me about ${name}`)} learnedTopics={learner.topics_covered} />
            </div>

            {/* Overlay UI */}
            <div className="absolute inset-0 z-10 pointer-events-none flex flex-col justify-between p-6 bg-gradient-to-b from-space-900/70 via-transparent to-space-900/85">

                {/* ── Header ── */}
                <header className="flex justify-between items-start pointer-events-auto">
                    <div className="space-y-1">
                        <h1 className="text-4xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-cyan-400">
                            ASTROVOICE <span className="text-cyan-400 font-light italic">NOVA</span>
                        </h1>
                        <div className="flex items-center gap-2 text-[10px] font-mono text-cyan-400 uppercase tracking-[0.2em]">
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#06b6d4] animate-pulse" />
                            {activeTab === 'chat' ? 'Nova 2 Sonic · Conversation' : 'Astro Academy · Learning Mode'}
                        </div>
                    </div>

                    {/* Tab Switcher */}
                    <div className="flex bg-white/5 rounded-full p-1 border border-white/10 backdrop-blur-md">
                        <button 
                            onClick={() => setActiveTab('chat')}
                            className={`px-5 py-2 rounded-full text-xs font-bold transition-all ${activeTab === 'chat' ? 'bg-white text-black' : 'text-white/40 hover:text-white'}`}
                        >
                            Conversation
                        </button>
                        <button 
                            onClick={() => setActiveTab('learning')}
                            className={`px-5 py-2 rounded-full text-xs font-bold transition-all ${activeTab === 'learning' ? 'bg-cyan-500 text-white' : 'text-white/40 hover:text-white'}`}
                        >
                            Academy
                        </button>
                    </div>
                </header>

                {/* ── Centre status ── */}
                <main className="flex-1 flex flex-col items-center justify-center -mt-8">
                    {activeTab === 'chat' ? (
                        <AnimatePresence mode="wait">
                            {status === 'recording' && (
                                <motion.div key="rec"
                                    initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                                    className="flex flex-col items-center gap-6"
                                >
                                    <div className="flex gap-1.5 items-end h-16">
                                        {[...Array(18)].map((_, i) => (
                                            <motion.div key={i}
                                                animate={{ height: [20, 60, 30, 50, 20] }}
                                                transition={{ repeat: Infinity, duration: 0.7, delay: i * 0.04 }}
                                                className="w-1.5 bg-gradient-to-t from-cyan-500 to-white rounded-full"
                                            />
                                        ))}
                                    </div>
                                    <p className="font-mono text-xs text-white/50 tracking-widest">NOVA SONIC RECEIVING</p>
                                </motion.div>
                            )}
                            {status === 'thinking' && (
                                <motion.div key="think"
                                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                    className="flex flex-col items-center gap-3"
                                >
                                    <Loader2 className="w-10 h-10 animate-spin text-cyan-400" />
                                    <p className="font-mono text-xs text-white/40 uppercase tracking-widest">Nova 2 Lite Reasoning…</p>
                                </motion.div>
                            )}
                            {status === 'speaking' && (
                                <motion.div key="speak"
                                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                    className="flex flex-col items-center gap-2"
                                >
                                    <Volume2 className="w-8 h-8 text-cyan-400 animate-pulse" />
                                    <p className="font-mono text-xs text-white/40 uppercase tracking-widest">Nova Sonic Responding</p>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    ) : (
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                            className="w-full max-w-4xl p-8 rounded-[40px] bg-black/40 border border-white/5 backdrop-blur-3xl flex flex-col items-center gap-8"
                        >
                            <div className="flex gap-8 w-full">
                                <div className={`flex-1 p-6 rounded-3xl border ${LEVEL_COLOR[learner.level]}`}>
                                    <h3 className="text-xs font-bold uppercase tracking-widest opacity-60 mb-1">Rank</h3>
                                    <p className="text-3xl font-black capitalize">{learner.level}</p>
                                    <p className="text-[10px] mt-2 opacity-60">{learner.correct_answers} correct answers out of {learner.total_exchanges} sessions</p>
                                </div>
                                <div className="flex-1 p-6 rounded-3xl bg-white/5 border border-white/10">
                                    <h3 className="text-xs font-bold uppercase tracking-widest opacity-60 mb-4">Concepts Mastered</h3>
                                    <div className="flex flex-wrap gap-2">
                                        {learner.topics_covered.length > 0 ? learner.topics_covered.map((t, i) => (
                                            <span key={i} className="px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300 text-[10px] font-bold border border-cyan-500/30 capitalize">
                                                {t}
                                            </span>
                                        )) : <span className="text-xs text-white/20">No topics explored yet.</span>}
                                    </div>
                                </div>
                            </div>

                            {checkQuestion ? (
                                <div className="w-full flex flex-col items-center">
                                    <div className="w-full p-8 rounded-3xl bg-cyan-500/10 border border-cyan-500/30 flex flex-col items-center text-center mb-6">
                                        <h3 className="text-[10px] font-bold uppercase text-cyan-400 tracking-widest mb-4">Current Academy Challenge</h3>
                                        <p className="text-xl font-medium text-white/90 mb-6">{checkQuestion}</p>
                                        <button 
                                            onClick={() => setQuizOpen(true)}
                                            className="px-8 py-3 rounded-full bg-cyan-500 text-white font-bold hover:bg-cyan-400 transition-all shadow-[0_0_30px_rgba(6,182,212,0.4)]"
                                        >
                                            {quizOpen ? 'Quiz in Progress' : 'Start Quiz'}
                                        </button>
                                    </div>

                                    {/* Inline Quiz Panel (Only in Academy Tab) */}
                                    <AnimatePresence>
                                        {quizOpen && (
                                            <motion.div 
                                                initial={{ opacity: 0, height: 0 }} 
                                                animate={{ opacity: 1, height: 'auto' }} 
                                                exit={{ opacity: 0, height: 0 }}
                                                className="w-full overflow-hidden"
                                            >
                                                <QuizPanel 
                                                    question={checkQuestion}
                                                    sessionId={sessionId.current}
                                                    onClose={() => setQuizOpen(false)}
                                                    onResult={(result) => {
                                                        if (result.learner) setLearner(result.learner)
                                                    }}
                                                />
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            ) : (
                                <div className="text-center opacity-40 py-12">
                                    <p>Ask Nova a question in the chat to generate a learning challenge.</p>
                                </div>
                            )}
                        </motion.div>
                    )}
                </main>

                {/* ── Bottom card + controls ── */}
                <footer className="w-full flex flex-col items-center gap-5 pointer-events-auto">

                    {/* Response card - ONLY SHOW IN CHAT TAB OR AS MINIMAL IN LEARNING */}
                    <AnimatePresence>
                        {response && activeTab === 'chat' && (
                            <motion.div
                                initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
                                className="w-full max-w-3xl p-7 rounded-[32px] bg-black/50 border border-white/10 backdrop-blur-[40px] relative overflow-hidden"
                            >
                                {/* top accent */}
                                <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-60" />

                                {/* transcript label */}
                                {transcript && (
                                    <p className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-3">
                                        Query: {transcript}
                                    </p>
                                )}

                                {/* Confidence */}
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="text-[9px] uppercase text-white/30 font-bold tracking-widest">Nova Confidence</div>
                                    <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden max-w-[160px]">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${confidence * 100}%` }}
                                            className="h-full bg-cyan-400"
                                        />
                                    </div>
                                    <span className="text-[10px] font-mono text-cyan-400 font-bold">
                                        {(confidence * 100).toFixed(0)}%
                                    </span>
                                </div>

                                {/* Answer */}
                                <p className="text-lg leading-relaxed font-medium text-white/90 whitespace-pre-wrap">{response}</p>

                                {/* Sources */}
                                {sources.length > 0 && (
                                    <div className="mt-5 border-t border-white/5 pt-4">
                                        <button
                                            onClick={() => setShowSources(s => !s)}
                                            className="text-[10px] uppercase text-white/30 font-bold hover:text-white flex items-center gap-1"
                                        >
                                            <ChevronUp className={`w-3 h-3 transition-transform ${showSources ? '' : 'rotate-180'}`} />
                                            {showSources ? 'Hide' : 'Show'} Sources ({sources.length})
                                        </button>
                                        {showSources && (
                                            <div className="mt-3 space-y-2">
                                                {sources.map((s, i) => (
                                                    <div key={i} className="px-4 py-3 rounded-xl bg-white/5 border border-white/5 text-xs">
                                                        <div className="font-bold text-white/80">[{i + 1}] {s.title}</div>
                                                        <div className="text-white/40 mt-0.5 line-clamp-2">{s.summary || s.abstract}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Search input */}
                    <AnimatePresence>
                        {showSearch && (
                            <motion.form
                                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}
                                onSubmit={handleSearchSubmit}
                                className="w-full max-w-md flex items-center gap-2 px-5 py-3 rounded-full bg-white/10 border border-white/20 backdrop-blur-xl"
                            >
                                <input
                                    autoFocus
                                    value={searchText}
                                    onChange={e => setSearchText(e.target.value)}
                                    placeholder="Ask anything about space…"
                                    className="flex-1 bg-transparent text-sm text-white placeholder:text-white/30 outline-none"
                                />
                                <button type="submit" className="text-cyan-400 hover:text-white transition-colors">
                                    <Search className="w-4 h-4" />
                                </button>
                                <button type="button" onClick={() => setShowSearch(false)} className="text-white/30 hover:text-white">
                                    <X className="w-4 h-4" />
                                </button>
                            </motion.form>
                        )}
                    </AnimatePresence>

                    {/* Control dock */}
                    <div className="flex items-center gap-8 bg-white/5 px-8 py-5 rounded-full border border-white/10 backdrop-blur-[60px] shadow-2xl">

                        {/* Search toggle */}
                        <button
                            onClick={() => setShowSearch(s => !s)}
                            className={`p-4 rounded-full transition-all ${showSearch ? 'bg-cyan-500/20 text-cyan-400' : 'text-white/40 hover:bg-white/10 hover:text-white'}`}
                        >
                            <Search className="w-6 h-6" />
                        </button>

                        {/* Mic — Nova Sonic */}
                        <button
                            onClick={toggleMic}
                            disabled={isBusy}
                            className={`relative p-10 rounded-full transition-all duration-500 active:scale-95 disabled:opacity-40 ${
                                micActive
                                    ? 'bg-red-500 shadow-[0_0_40px_rgba(239,68,68,0.5)] scale-110'
                                    : 'bg-white shadow-[0_0_40px_rgba(255,255,255,0.15)]'
                            }`}
                        >
                            {micActive
                                ? <MicOff className="w-10 h-10 text-white" />
                                : <Mic    className="w-10 h-10 text-black" />}
                            {/* Pulse ring when recording */}
                            {micActive && (
                                <span className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-25" />
                            )}
                        </button>

                        {/* Topics count / hint */}
                        <div className="flex flex-col items-center text-white/30 text-[9px] font-mono uppercase tracking-widest">
                            <span className="text-lg font-bold text-white/60">{learner.correct_answers}</span>
                            correct
                        </div>
                    </div>
                </footer>
            </div>

            {/* Removed root-level QuizPanel modal to keep conversation strictly conversational */}

            {/* Ambient glows */}
            <motion.div animate={{ scale: [1, 1.15, 1], x: [0, 40, 0] }} transition={{ repeat: Infinity, duration: 22 }}
                className="absolute top-1/4 -left-40 w-[500px] h-[500px] bg-cyan-500/8 rounded-full blur-[140px] pointer-events-none" />
            <motion.div animate={{ scale: [1.1, 1, 1.1], x: [0, -40, 0] }} transition={{ repeat: Infinity, duration: 17 }}
                className="absolute bottom-1/4 -right-40 w-[500px] h-[500px] bg-violet-500/8 rounded-full blur-[140px] pointer-events-none" />
        </div>
    )
}

export default App
