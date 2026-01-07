'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'

// 일반 img 태그를 사용하는 프로필 이미지 컴포넌트
// Instagram CDN 이미지는 CORS 문제로 직접 로드할 수 없으므로 프록시를 통해 로드
function ProfileImage({ 
  src, 
  alt, 
  className, 
  onError 
}: { 
  src: string
  alt: string
  className?: string
  onError?: (e: React.SyntheticEvent<HTMLImageElement, Event>) => void
}) {
  // 프록시 URL 생성
  const proxyUrl = src ? `/api/image-proxy?url=${encodeURIComponent(src)}` : null
  
  if (!proxyUrl) {
    return null
  }
  
  return (
    <img
      src={proxyUrl}
      alt={alt}
      className={className}
      onError={(e) => {
        onError?.(e)
      }}
      loading="lazy"
    />
  )
}

interface Reel {
  id: number
  reel_id: string
  link: string
  thumbnail_url: string | null
  author: string | null
  creator_profile_image: string | null
  title: string | null
  music: string | null
  likes: number | null
  comments: number | null
  views: number | null
  recorded_at: string | null
}

interface Metric {
  id: number
  likes: number | null
  comments: number | null
  views: number | null
  recorded_at: string
}

interface MetricModalProps {
  reel: Reel
  onClose: () => void
}

export default function MetricModal({ reel, onClose }: MetricModalProps) {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [loading, setLoading] = useState(true)
  const [imageError, setImageError] = useState(false)
  const [profileImageError, setProfileImageError] = useState(false)

  useEffect(() => {
    fetchMetrics()
  }, [reel.reel_id])

  const fetchMetrics = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/reels/${reel.reel_id}/metrics`)
      const result = await response.json()
      if (result.success) {
        setMetrics(result.data.metrics)
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number | null): string => {
    if (num === null) return '0'
    if (num >= 10000) {
      return `${(num / 10000).toFixed(1)}만`
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}천`
    }
    return num.toString()
  }

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const calculateChange = (current: number | null, previous: number | null): number | null => {
    if (current === null || previous === null || previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="sticky top-0 bg-gray-800 border-b border-gray-700 p-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-white">통계 추적</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>

        {/* 릴스 정보 */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex gap-4">
            {reel.thumbnail_url && !imageError ? (
              <div className="relative w-32 h-48 rounded-lg overflow-hidden flex-shrink-0">
                <img
                  src={reel.thumbnail_url}
                  alt={reel.title || 'Reel thumbnail'}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    const img = e.currentTarget
                    if (!img.src.includes('/api/image-proxy')) {
                      img.src = `/api/image-proxy?url=${encodeURIComponent(reel.thumbnail_url || '')}`
                    } else {
                      setImageError(true)
                    }
                  }}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  crossOrigin="anonymous"
                />
              </div>
            ) : (
              <div className="w-32 h-48 rounded-lg bg-gray-700 flex items-center justify-center text-gray-500 flex-shrink-0">
                No Image
              </div>
            )}
            <div className="flex-1">
              {reel.author && (
                <div className="flex items-center gap-2 mb-2">
                  {reel.creator_profile_image && !profileImageError ? (
                    <div className="w-10 h-10 rounded-full overflow-hidden bg-gray-700 flex-shrink-0">
                      <ProfileImage
                        src={reel.creator_profile_image}
                        alt={reel.author || 'Profile'}
                        className="w-full h-full object-cover"
                        onError={() => {
                          setProfileImageError(true)
                        }}
                      />
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                      <span className="text-gray-400 text-sm">
                        {reel.author.charAt(0).toUpperCase()}
                      </span>
                    </div>
                  )}
                  <span className="text-white font-semibold">@{reel.author}</span>
                </div>
              )}
              {reel.title && (
                <p className="text-gray-300 mb-2">{reel.title}</p>
              )}
              {reel.music && (
                <p className="text-gray-400 text-sm mb-2">🎵 {reel.music}</p>
              )}
              <a
                href={reel.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 text-sm"
              >
                인스타그램에서 보기 →
              </a>
            </div>
          </div>
        </div>

        {/* 통계 테이블 */}
        <div className="p-6">
          <h3 className="text-xl font-bold text-white mb-4">추적 히스토리</h3>
          {loading ? (
            <div className="text-center text-gray-400 py-8">로딩 중...</div>
          ) : metrics.length === 0 ? (
            <div className="text-center text-gray-400 py-8">추적 데이터가 없습니다.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="pb-3 text-gray-400 font-semibold">기록 시간</th>
                    <th className="pb-3 text-gray-400 font-semibold">조회수</th>
                    <th className="pb-3 text-gray-400 font-semibold">좋아요</th>
                    <th className="pb-3 text-gray-400 font-semibold">댓글</th>
                    <th className="pb-3 text-gray-400 font-semibold">변화율</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((metric, index) => {
                    const previousMetric = index < metrics.length - 1 ? metrics[index + 1] : null
                    const viewsChange = calculateChange(metric.views, previousMetric?.views ?? null)
                    const likesChange = calculateChange(metric.likes, previousMetric?.likes ?? null)
                    const commentsChange = calculateChange(metric.comments, previousMetric?.comments ?? null)

                    return (
                      <tr key={metric.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                        <td className="py-3 text-gray-300">{formatDate(metric.recorded_at)}</td>
                        <td className="py-3 text-white font-semibold">
                          {formatNumber(metric.views)}
                          {viewsChange !== null && (
                            <span className={`ml-2 text-xs ${viewsChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {viewsChange >= 0 ? '+' : ''}{viewsChange.toFixed(1)}%
                            </span>
                          )}
                        </td>
                        <td className="py-3 text-white font-semibold">
                          {formatNumber(metric.likes)}
                          {likesChange !== null && (
                            <span className={`ml-2 text-xs ${likesChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {likesChange >= 0 ? '+' : ''}{likesChange.toFixed(1)}%
                            </span>
                          )}
                        </td>
                        <td className="py-3 text-white font-semibold">
                          {formatNumber(metric.comments)}
                          {commentsChange !== null && (
                            <span className={`ml-2 text-xs ${commentsChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {commentsChange >= 0 ? '+' : ''}{commentsChange.toFixed(1)}%
                            </span>
                          )}
                        </td>
                        <td className="py-3 text-gray-400 text-sm">
                          {previousMetric && (
                            <div className="flex flex-col gap-1">
                              {viewsChange !== null && (
                                <span className={viewsChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                                  조회수 {viewsChange >= 0 ? '+' : ''}{viewsChange.toFixed(1)}%
                                </span>
                              )}
                              {likesChange !== null && (
                                <span className={likesChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                                  좋아요 {likesChange >= 0 ? '+' : ''}{likesChange.toFixed(1)}%
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

