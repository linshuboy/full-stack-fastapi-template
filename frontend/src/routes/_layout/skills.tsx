import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download, FolderOpen } from "lucide-react"

import {
  SkillCategoriesService,
  SkillsService,
  type SkillCategoryPublic,
  type SkillPublic,
} from "@/client"
import AddSkill from "@/components/Skills/AddSkill"
import ManageSkillCategories from "@/components/Skills/ManageSkillCategories"
import SkillActionsMenu from "@/components/Skills/SkillActionsMenu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getSkillCategoriesQueryOptions(includeInactive: boolean) {
  return {
    queryFn: () =>
      SkillCategoriesService.readSkillCategories({
        skip: 0,
        limit: 200,
        includeInactive,
      }),
    queryKey: ["skill-categories", includeInactive],
  }
}

function getSkillsQueryOptions(canManage: boolean) {
  return {
    queryFn: () =>
      SkillsService.readSkills({
        skip: 0,
        limit: 200,
        onlyPublished: !canManage,
      }),
    queryKey: ["skills", canManage],
  }
}

export const Route = createFileRoute("/_layout/skills")({
  component: Skills,
  head: () => ({
    meta: [
      {
        title: "技能 - 齐力 AI 技能平台",
      },
    ],
  }),
})

const formatFileSize = (size: number) => {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (value?: string | null) => {
  if (!value) {
    return "-"
  }
  return new Date(value).toLocaleString()
}

function SkillsTable({
  canManage,
  categories,
  skills,
}: {
  canManage: boolean
  categories: SkillCategoryPublic[]
  skills: SkillPublic[]
}) {
  const { showErrorToast } = useCustomToast()

  const downloadMutation = useMutation({
    mutationFn: async (skillId: string) =>
      SkillsService.getSkillDownload({ skillId }),
    onSuccess: (data) => {
      window.open(data.url, "_blank", "noopener,noreferrer")
    },
    onError: handleError.bind(showErrorToast),
  })

  if (skills.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FolderOpen className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">暂无技能包</h3>
        <p className="text-muted-foreground">上传压缩包后会显示在这里</p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名称</TableHead>
          <TableHead>分类</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>文件</TableHead>
          <TableHead>大小</TableHead>
          <TableHead>创建时间</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {skills.map((skill) => (
          <TableRow key={skill.id}>
            <TableCell className="max-w-[220px] truncate">{skill.title}</TableCell>
            <TableCell>{skill.category_name}</TableCell>
            <TableCell>
              {skill.is_published ? <Badge>已上架</Badge> : <Badge variant="secondary">未上架</Badge>}
            </TableCell>
            <TableCell className="max-w-[220px] truncate">{skill.file_name}</TableCell>
            <TableCell>{formatFileSize(skill.file_size)}</TableCell>
            <TableCell>{formatDate(skill.created_at)}</TableCell>
            <TableCell className="text-right">
              <div className="flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadMutation.mutate(skill.id)}
                >
                  <Download className="mr-1 h-4 w-4" />
                  下载
                </Button>
                {canManage ? (
                  <SkillActionsMenu categories={categories} skill={skill} />
                ) : null}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Skills() {
  const { user: currentUser } = useAuth()
  const canManage = currentUser?.is_superuser ?? false

  const categoriesQuery = useQuery(
    getSkillCategoriesQueryOptions(canManage),
  )
  const skillsQuery = useQuery(getSkillsQueryOptions(canManage))

  const categories = categoriesQuery.data?.data ?? []
  const skills = skillsQuery.data?.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">技能仓库</h1>
          <p className="text-muted-foreground">
            上传并维护技能压缩包，支持上架/下架和分类管理
          </p>
        </div>
        {canManage ? (
          <div className="flex items-center gap-2">
            <ManageSkillCategories categories={categories} />
            <AddSkill categories={categories.filter((item) => item.is_active)} />
          </div>
        ) : null}
      </div>

      {categoriesQuery.isLoading || skillsQuery.isLoading ? (
        <div className="text-sm text-muted-foreground">正在加载技能仓库数据...</div>
      ) : (
        <SkillsTable canManage={canManage} categories={categories} skills={skills} />
      )}
    </div>
  )
}
