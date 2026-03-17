import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Upload } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { type SkillPublic, SkillsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ReplaceSkillFileProps {
  skill: SkillPublic
}

const ReplaceSkillFile = ({ skill }: ReplaceSkillFileProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit, reset } = useForm()

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) {
        throw new Error("请先选择一个压缩包文件")
      }
      await SkillsService.replaceSkillFile({
        skillId: skill.id,
        formData: { file },
      })
    },
    onSuccess: () => {
      showSuccessToast("压缩包文件已更新")
      setIsOpen(false)
      setFile(null)
      reset()
    },
    onError: (err) => {
      if (err instanceof Error && err.message === "请先选择一个压缩包文件") {
        showErrorToast(err.message)
        return
      }
      handleError.call(showErrorToast, err as any)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] })
    },
  })

  const onSubmit = async () => mutation.mutate()

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(event) => event.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Upload />
        替换压缩包
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>替换压缩包</DialogTitle>
            <DialogDescription>
              当前文件：`{skill.file_name}`。支持 `.zip` / `.tar` / `.tar.gz` / `.tgz`。
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              type="file"
              accept=".zip,.tar,.tar.gz,.tgz"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton type="submit" loading={mutation.isPending}>
              替换
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default ReplaceSkillFile
