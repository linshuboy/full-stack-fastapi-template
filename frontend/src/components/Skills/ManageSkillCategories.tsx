import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Edit, Plus, Save, Trash2, X } from "lucide-react"
import { useState } from "react"

import { SkillCategoriesService, type SkillCategoryPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ManageSkillCategoriesProps {
  categories: SkillCategoryPublic[]
}

const ManageSkillCategories = ({ categories }: ManageSkillCategoriesProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [sortOrder, setSortOrder] = useState("0")
  const [isActive, setIsActive] = useState(true)
  const [editingCategory, setEditingCategory] = useState<SkillCategoryPublic | null>(
    null,
  )
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const refreshQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["skill-categories"] })
    queryClient.invalidateQueries({ queryKey: ["skills"] })
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      await SkillCategoriesService.createSkillCategory({
        requestBody: {
          name,
          description,
          sort_order: Number.parseInt(sortOrder || "0", 10),
          is_active: isActive,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("分类创建成功")
      setName("")
      setDescription("")
      setSortOrder("0")
      setIsActive(true)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: refreshQueries,
  })

  const updateMutation = useMutation({
    mutationFn: async (category: SkillCategoryPublic) => {
      await SkillCategoriesService.updateSkillCategory({
        categoryId: category.id,
        requestBody: {
          name: category.name,
          description: category.description,
          sort_order: category.sort_order,
          is_active: category.is_active,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("分类更新成功")
      setEditingCategory(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: refreshQueries,
  })

  const deleteMutation = useMutation({
    mutationFn: async (categoryId: string) => {
      await SkillCategoriesService.deleteSkillCategory({ categoryId })
    },
    onSuccess: () => {
      showSuccessToast("分类删除成功")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: refreshQueries,
  })

  const handleDelete = (category: SkillCategoryPublic) => {
    if (!window.confirm(`确认删除分类「${category.name}」吗？`)) {
      return
    }
    deleteMutation.mutate(category.id)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">管理分类</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>技能分类管理</DialogTitle>
          <DialogDescription>
            可新增、编辑、删除分类。默认分类已经初始化，可继续维护。
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1.2fr_1.2fr_0.7fr_auto_auto]">
          <Input
            value={name}
            placeholder="分类名称"
            onChange={(event) => setName(event.target.value)}
          />
          <Input
            value={description}
            placeholder="描述（可选）"
            onChange={(event) => setDescription(event.target.value)}
          />
          <Input
            value={sortOrder}
            placeholder="排序"
            onChange={(event) => setSortOrder(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <Checkbox
              checked={isActive}
              onCheckedChange={(value) => setIsActive(value === true)}
            />
            <span className="text-sm text-muted-foreground">启用</span>
          </div>
          <LoadingButton
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            <Plus className="mr-2 h-4 w-4" />
            新增
          </LoadingButton>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>描述</TableHead>
              <TableHead>排序</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {categories.map((category) => {
              const isEditing = editingCategory?.id === category.id
              return (
                <TableRow key={category.id}>
                  <TableCell>
                    {isEditing ? (
                      <Input
                        value={editingCategory.name}
                        onChange={(event) =>
                          setEditingCategory((current) =>
                            current
                              ? { ...current, name: event.target.value }
                              : current,
                          )
                        }
                      />
                    ) : (
                      category.name
                    )}
                  </TableCell>
                  <TableCell>
                    {isEditing ? (
                      <Input
                        value={editingCategory.description ?? ""}
                        onChange={(event) =>
                          setEditingCategory((current) =>
                            current
                              ? { ...current, description: event.target.value }
                              : current,
                          )
                        }
                      />
                    ) : (
                      <span className="text-muted-foreground">
                        {category.description || "-"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {isEditing ? (
                      <Input
                        value={String(editingCategory.sort_order ?? 0)}
                        onChange={(event) =>
                          setEditingCategory((current) =>
                            current
                              ? {
                                  ...current,
                                  sort_order: Number.parseInt(
                                    event.target.value || "0",
                                    10,
                                  ),
                                }
                              : current,
                          )
                        }
                      />
                    ) : (
                      String(category.sort_order ?? 0)
                    )}
                  </TableCell>
                  <TableCell>
                    {isEditing ? (
                      <div className="flex items-center gap-2">
                        <Checkbox
                          checked={editingCategory.is_active}
                          onCheckedChange={(value) =>
                            setEditingCategory((current) =>
                              current
                                ? { ...current, is_active: value === true }
                                : current,
                            )
                          }
                        />
                        <span className="text-sm text-muted-foreground">启用</span>
                      </div>
                    ) : category.is_active ? (
                      <Badge>启用</Badge>
                    ) : (
                      <Badge variant="secondary">停用</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {isEditing ? (
                        <>
                          <LoadingButton
                            loading={updateMutation.isPending}
                            size="sm"
                            onClick={() => updateMutation.mutate(editingCategory)}
                          >
                            <Save className="h-4 w-4" />
                          </LoadingButton>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingCategory(null)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingCategory(category)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDelete(category)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </DialogContent>
    </Dialog>
  )
}

export default ManageSkillCategories
