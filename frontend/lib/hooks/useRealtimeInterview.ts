'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { API_BASE_URL } from '@/lib/hooks/useAuthFetch';

interface TranscriptTurn {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
}

interface RealtimeInterviewState {
    isConnected: boolean;
    isRecording: boolean;
    error: string | null;
    transcript: TranscriptTurn[];
    sessionId: string | null;
    connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
}

interface UseRealtimeInterviewOptions {
    onTranscriptUpdate?: (transcript: TranscriptTurn[]) => void;
    onConnectionChange?: (connected: boolean) => void;
    onError?: (error: string) => void;
}

/**
 * Custom hook for managing OpenAI Realtime WebRTC interview sessions.
 * 
 * SECURITY: Uses ephemeral client_secret from backend - never exposes API key to browser.
 */
export function useRealtimeInterview(options: UseRealtimeInterviewOptions = {}) {
    const [state, setState] = useState<RealtimeInterviewState>({
        isConnected: false,
        isRecording: false,
        error: null,
        transcript: [],
        sessionId: null,
        connectionStatus: 'disconnected',
    });

    const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
    const dataChannelRef = useRef<RTCDataChannel | null>(null);
    const audioElementRef = useRef<HTMLAudioElement | null>(null);
    const mediaStreamRef = useRef<MediaStream | null>(null);
    const interviewSessionIdRef = useRef<string | null>(null);
    const startTimeRef = useRef<number | null>(null);

    /**
     * Get access token from Supabase session
     */
    const getAccessToken = useCallback(async (): Promise<string> => {
        const { getSupabaseClient } = await import('@/lib/supabase/client');
        const supabase = getSupabaseClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) {
            throw new Error('Not authenticated');
        }
        return session.access_token;
    }, []);

    /**
     * Create interview session and get context bundle
     */
    const createInterviewSession = useCallback(async (accessToken: string) => {
        const response = await fetch(`${API_BASE_URL}/api/interview/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`,
            },
            body: JSON.stringify({}),
        });

        if (!response.ok) {
            throw new Error('Failed to create interview session');
        }

        return response.json();
    }, []);

    /**
     * Get ephemeral Realtime session credentials from backend
     */
    const getEphemeralCredentials = useCallback(async (
        accessToken: string,
        systemPrompt: string
    ) => {
        const response = await fetch(`${API_BASE_URL}/api/interview/realtime/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`,
            },
            body: JSON.stringify({
                system_prompt: systemPrompt,
                voice: 'alloy',
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to get Realtime credentials');
        }

        return response.json();
    }, []);

    /**
     * Handle incoming Realtime events
     */
    const handleRealtimeEvent = useCallback((event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case 'response.audio_transcript.delta':
                    // Partial assistant transcript
                    break;

                case 'response.audio_transcript.done':
                    // Complete assistant turn
                    const assistantContent = data.transcript || '';
                    if (assistantContent.trim()) {
                        setState(prev => ({
                            ...prev,
                            transcript: [
                                ...prev.transcript,
                                {
                                    role: 'assistant',
                                    content: assistantContent,
                                    timestamp: new Date().toISOString(),
                                }
                            ]
                        }));
                        options.onTranscriptUpdate?.(state.transcript);
                    }
                    break;

                case 'conversation.item.input_audio_transcription.completed':
                    // User speech transcribed
                    const userContent = data.transcript || '';
                    if (userContent.trim()) {
                        setState(prev => ({
                            ...prev,
                            transcript: [
                                ...prev.transcript,
                                {
                                    role: 'user',
                                    content: userContent,
                                    timestamp: new Date().toISOString(),
                                }
                            ]
                        }));
                        options.onTranscriptUpdate?.(state.transcript);
                    }
                    break;

                case 'error':
                    console.error('Realtime error:', data.error);
                    setState(prev => ({ ...prev, error: data.error?.message || 'Realtime error' }));
                    options.onError?.(data.error?.message || 'Realtime error');
                    break;
            }
        } catch (err) {
            console.error('Error parsing Realtime event:', err);
        }
    }, [options, state.transcript]);

    /**
     * Start the interview session
     */
    const startInterview = useCallback(async () => {
        try {
            setState(prev => ({ ...prev, connectionStatus: 'connecting', error: null }));

            // 1. Get auth token
            const accessToken = await getAccessToken();

            // 2. Create interview session with context
            const session = await createInterviewSession(accessToken);
            interviewSessionIdRef.current = session.session_id;

            setState(prev => ({
                ...prev,
                sessionId: session.session_id,
            }));

            // 3. Get ephemeral Realtime credentials
            const credentials = await getEphemeralCredentials(accessToken, session.system_prompt);

            // 4. Request microphone access
            const mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });
            mediaStreamRef.current = mediaStream;

            // 5. Create WebRTC peer connection
            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
            });
            peerConnectionRef.current = pc;

            // 6. Set up audio playback
            const audioElement = document.createElement('audio');
            audioElement.autoplay = true;
            audioElementRef.current = audioElement;

            pc.ontrack = (event) => {
                audioElement.srcObject = event.streams[0];
            };

            // 7. Add microphone track
            const audioTrack = mediaStream.getAudioTracks()[0];
            pc.addTrack(audioTrack, mediaStream);

            // 8. Create data channel for events
            const dataChannel = pc.createDataChannel('oai-events');
            dataChannelRef.current = dataChannel;

            dataChannel.onmessage = handleRealtimeEvent;
            dataChannel.onopen = () => {
                console.log('Data channel opened');
                // Enable audio transcription
                dataChannel.send(JSON.stringify({
                    type: 'input_audio_transcription.create',
                    input_audio_transcription: { model: 'whisper-1' }
                }));
            };

            // 9. Create and set local description (offer)
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // 10. Send offer to OpenAI Realtime API
            const sdpResponse = await fetch('https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${credentials.client_secret}`,
                    'Content-Type': 'application/sdp',
                },
                body: offer.sdp,
            });

            if (!sdpResponse.ok) {
                throw new Error('Failed to establish WebRTC connection with OpenAI');
            }

            // 11. Set remote description (answer)
            const answerSdp = await sdpResponse.text();
            await pc.setRemoteDescription({
                type: 'answer',
                sdp: answerSdp,
            });

            startTimeRef.current = Date.now();

            setState(prev => ({
                ...prev,
                isConnected: true,
                isRecording: true,
                connectionStatus: 'connected',
            }));

            options.onConnectionChange?.(true);

        } catch (error) {
            console.error('Failed to start interview:', error);
            const errorMessage = error instanceof Error ? error.message : 'Failed to start interview';

            if (errorMessage.includes('Permission denied') || errorMessage.includes('NotAllowedError')) {
                setState(prev => ({
                    ...prev,
                    error: 'Microphone access denied. Please allow microphone access and try again.',
                    connectionStatus: 'error',
                }));
            } else {
                setState(prev => ({
                    ...prev,
                    error: errorMessage,
                    connectionStatus: 'error',
                }));
            }

            options.onError?.(errorMessage);
        }
    }, [getAccessToken, createInterviewSession, getEphemeralCredentials, handleRealtimeEvent, options]);

    /**
     * Stop the interview and finalize
     */
    const stopInterview = useCallback(async () => {
        // Calculate duration
        const duration = startTimeRef.current
            ? Math.floor((Date.now() - startTimeRef.current) / 1000)
            : 0;

        // Close WebRTC connection
        if (dataChannelRef.current) {
            dataChannelRef.current.close();
            dataChannelRef.current = null;
        }

        if (peerConnectionRef.current) {
            peerConnectionRef.current.close();
            peerConnectionRef.current = null;
        }

        // Stop media tracks
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach(track => track.stop());
            mediaStreamRef.current = null;
        }

        // Clean up audio element
        if (audioElementRef.current) {
            audioElementRef.current.srcObject = null;
            audioElementRef.current = null;
        }

        // Finalize session with backend
        if (interviewSessionIdRef.current && state.transcript.length > 0) {
            try {
                const accessToken = await getAccessToken();

                await fetch(`${API_BASE_URL}/api/interview/sessions/${interviewSessionIdRef.current}/finalize`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${accessToken}`,
                    },
                    body: JSON.stringify({
                        transcript: state.transcript,
                        duration_seconds: duration,
                    }),
                });
            } catch (error) {
                console.error('Failed to finalize interview:', error);
            }
        }

        setState(prev => ({
            ...prev,
            isConnected: false,
            isRecording: false,
            connectionStatus: 'disconnected',
        }));

        options.onConnectionChange?.(false);

    }, [state.transcript, getAccessToken, options]);

    /**
     * Clean up on unmount
     */
    useEffect(() => {
        return () => {
            if (peerConnectionRef.current) {
                peerConnectionRef.current.close();
            }
            if (mediaStreamRef.current) {
                mediaStreamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    return {
        ...state,
        startInterview,
        stopInterview,
        clearTranscript: () => setState(prev => ({ ...prev, transcript: [] })),
    };
}

export type { TranscriptTurn, RealtimeInterviewState };
