'use client'

import { useEffect, useState } from 'react'
import ReelCard from '@/components/ReelCard'
import MetricModal from '@/components/MetricModal'

interface Reel {
  id: number
  reel_id: string
  link: string
  thumbnail_url: string | null
  author: string | null
  creator_profile_image: string | null
  title: string | null
  music: string | null
  country_code: string | null
  likes: number | null
  comments: number | null
  views: number | null
  recorded_at: string | null
  created_at: string
}

interface WeekGroup {
  weekStart: Date
  weekEnd: Date
  reels: Reel[]
}

// 국가 코드 → 한글 표기 (프론트 전용, API에는 kr/jp 그대로 전달)
const COUNTRY_LABELS: Record<string, string> = {
  kr: '한국',
  jp: '일본',
}

export default function Home() {
  const [reels, setReels] = useState<Reel[]>([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState<'views' | 'likes'>('likes')
  const [selectedReel, setSelectedReel] = useState<Reel | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [country, setCountry] = useState<string>('') // 빈 값 = 전체
  const [countries, setCountries] = useState<string[]>([])

  useEffect(() => {
    fetch('/api/countries')
      .then((res) => res.json())
      .then((result) => result.success && result.data?.length && setCountries(result.data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchReels()
  }, [sortBy, startDate, endDate, country])

  const fetchReels = async () => {
    setLoading(true)
    try {
      let url = `/api/reels/ranking?sortBy=${sortBy}&limit=1000`
      if (country) {
        url += `&country=${encodeURIComponent(country)}`
      }
      if (startDate) {
        url += `&startDate=${startDate}`
      }
      if (endDate) {
        url += `&endDate=${endDate}`
      }
      const response = await fetch(url)
      const result = await response.json()
      if (result.success) {
        setReels(result.data)
      }
    } catch (error) {
      console.error('Failed to fetch reels:', error)
    } finally {
      setLoading(false)
    }
  }

  // 수집일(recorded_at) 기준 일주일 단위 그룹화 (없으면 created_at 사용)
  const groupByWeek = (reels: Reel[]): WeekGroup[] => {
    if (reels.length === 0) return []

    const weekMap = new Map<string, Reel[]>()

    reels.forEach((reel) => {
      const dateStr = reel.recorded_at || reel.created_at
      const date = new Date(dateStr)
      const dayOfWeek = date.getDay()
      const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
      const weekStart = new Date(date)
      weekStart.setDate(date.getDate() + diff)
      weekStart.setHours(0, 0, 0, 0)

      const weekKey = weekStart.toISOString().split('T')[0]
      if (!weekMap.has(weekKey)) {
        weekMap.set(weekKey, [])
      }
      weekMap.get(weekKey)!.push(reel)
    })

    // 주별로 정렬 (최신순)
    const sortedWeeks = Array.from(weekMap.entries()).sort((a, b) => 
      new Date(b[0]).getTime() - new Date(a[0]).getTime()
    )

    return sortedWeeks.map(([weekKey, weekReels]) => {
      const weekStart = new Date(weekKey)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      weekEnd.setHours(23, 59, 59, 999)
      
      return {
        weekStart,
        weekEnd,
        reels: weekReels.sort((a, b) => {
          if (sortBy === 'likes') {
            return (b.likes || 0) - (a.likes || 0)
          }
          return (b.views || 0) - (a.views || 0)
        }),
      }
    })
  }

  const handleReelClick = (reel: Reel) => {
    setSelectedReel(reel)
    setShowModal(true)
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
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  // "2월 첫째 주 (2.15 ~ 2.21)" 형식
  const formatWeekLabel = (weekStart: Date, weekEnd: Date): string => {
    const month = weekStart.getMonth() + 1
    const dayOfMonth = weekStart.getDate()
    const weekOfMonth = Math.ceil(dayOfMonth / 7)
    const orderLabels = ['', '첫째', '둘째', '셋째', '넷째', '다섯째']
    const order = orderLabels[weekOfMonth] || `${weekOfMonth}째`
    const startShort = `${month}.${weekStart.getDate()}`
    const endShort = `${weekEnd.getMonth() + 1}.${weekEnd.getDate()}`
    return `${month}월 ${order} 주 (${startShort} ~ ${endShort})`
  }

  const weekGroups = groupByWeek(reels)

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold text-white mb-6 text-center">
          Instagram Reels Ranking
        </h1>

        {/* 필터 카드 */}
        <div className="mb-10 rounded-2xl bg-gray-800/80 border border-gray-700/80 shadow-xl p-6 backdrop-blur-sm">
          <div className="flex flex-col lg:flex-row lg:items-end gap-6 lg:gap-8 flex-wrap">
            {/* 국가 */}
            <div className="flex flex-col gap-1.5 min-w-[140px]">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">국가</span>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-gray-700/90 text-white border border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-shadow"
              >
                <option value="">전체</option>
                {countries.map((c) => (
                  <option key={c} value={c}>
                    {COUNTRY_LABELS[c] ?? c}
                  </option>
                ))}
              </select>
            </div>

            {/* 구분선 (데스크톱) */}
            <div className="hidden lg:block w-px h-10 bg-gray-600 self-center" aria-hidden />

            {/* 정렬 */}
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">정렬</span>
              <div className="flex rounded-xl bg-gray-700/90 p-1 border border-gray-600">
                <button
                  type="button"
                  onClick={() => setSortBy('likes')}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                    sortBy === 'likes'
                      ? 'bg-primary-500 text-white shadow-md'
                      : 'text-gray-400 hover:text-white hover:bg-gray-600/50'
                  }`}
                >
                  좋아요 순
                </button>
                <button
                  type="button"
                  onClick={() => setSortBy('views')}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                    sortBy === 'views'
                      ? 'bg-primary-500 text-white shadow-md'
                      : 'text-gray-400 hover:text-white hover:bg-gray-600/50'
                  }`}
                >
                  조회수 순
                </button>
              </div>
            </div>

            {/* 구분선 (데스크톱) */}
            <div className="hidden lg:block w-px h-10 bg-gray-600 self-center" aria-hidden />

            {/* 날짜 범위 */}
            <div className="flex flex-col sm:flex-row gap-4 sm:gap-4 flex-1">
              <div className="flex flex-col gap-1.5 min-w-[120px]">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">시작일</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="px-4 py-2.5 rounded-xl bg-gray-700/90 text-white border border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-shadow [color-scheme:dark]"
                />
              </div>
              <div className="flex flex-col gap-1.5 min-w-[120px]">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">종료일</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="px-4 py-2.5 rounded-xl bg-gray-700/90 text-white border border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-shadow [color-scheme:dark]"
                />
              </div>
              {(startDate || endDate) && (
                <button
                  type="button"
                  onClick={() => {
                    setStartDate('')
                    setEndDate('')
                  }}
                  className="self-end px-4 py-2.5 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-600/50 border border-gray-600 hover:border-gray-500 transition-colors"
                >
                  초기화
                </button>
              )}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="text-white text-xl">로딩 중...</div>
          </div>
        ) : weekGroups.length === 0 ? (
          <div className="text-center text-gray-400 mt-12">
            데이터가 없습니다.
          </div>
        ) : (
          <div className="space-y-12">
            {weekGroups.map((week, weekIndex) => (
              <div key={weekIndex} className="space-y-4">
                <div className="border-b border-gray-700 pb-2">
                  <h2 className="text-2xl font-bold text-white">
                    {formatWeekLabel(week.weekStart, week.weekEnd)}
                  </h2>
                  <p className="text-gray-400 text-sm mt-1">
                    {week.weekStart.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })} ~ {week.weekEnd.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })} · 총 {week.reels.length}개 릴스
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {week.reels.map((reel, index) => (
                    <ReelCard
                      key={reel.id}
                      reel={reel}
                      rank={index + 1}
                      onClick={() => handleReelClick(reel)}
                      formatNumber={formatNumber}
                      formatDate={formatDate}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && selectedReel && (
        <MetricModal
          reel={selectedReel}
          onClose={() => {
            setShowModal(false)
            setSelectedReel(null)
          }}
        />
      )}
    </main>
  )
}

