import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type SkillCategoryPublic, SkillsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  title: z.string().min(1, { message: "名称不能为空" }),
  description: z.string().optional(),
  category_id: z.string().min(1, { message: "请选择分类" }),
  is_published: z.boolean(),
})

type FormData = z.infer<typeof formSchema>

interface AddSkillProps {
  categories: SkillCategoryPublic[]
}

const AddSkill = ({ categories }: AddSkillProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      title: "",
      description: "",
      category_id: "",
      is_published: true,
    },
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      if (!file) {
        throw new Error("请上传压缩包文件")
      }
      await SkillsService.createSkill({
        formData: {
          title: data.title,
          description: data.description,
          category_id: data.category_id,
          is_published: data.is_published,
          file,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("技能包创建成功")
      form.reset()
      setFile(null)
      setIsOpen(false)
    },
    onError: (err) => {
      if (err instanceof Error && err.message === "请上传压缩包文件") {
        showErrorToast(err.message)
        return
      }
      handleError.call(showErrorToast, err as any)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] })
    },
  })

  const onSubmit = (data: FormData) => mutation.mutate(data)

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          新增技能包
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新增技能包</DialogTitle>
          <DialogDescription>
            上传 `.zip` / `.tar` / `.tar.gz` / `.tgz` 压缩包并设置分类。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      名称 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="技能包名称" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>描述</FormLabel>
                    <FormControl>
                      <Input placeholder="可选描述" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="category_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      分类 <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value || undefined}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="请选择分类" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {categories.map((category) => (
                          <SelectItem key={category.id} value={category.id}>
                            {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormItem>
                <FormLabel>
                  压缩包 <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <Input
                    type="file"
                    accept=".zip,.tar,.tar.gz,.tgz"
                    onChange={(event) => {
                      const selectedFile = event.target.files?.[0]
                      setFile(selectedFile ?? null)
                    }}
                  />
                </FormControl>
              </FormItem>

              <FormField
                control={form.control}
                name="is_published"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">创建后立即上架</FormLabel>
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddSkill
