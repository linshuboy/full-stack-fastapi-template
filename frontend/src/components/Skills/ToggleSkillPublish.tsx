import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, EyeOff } from "lucide-react"

import { type SkillPublic, SkillsService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ToggleSkillPublishProps {
  skill: SkillPublic
}

const ToggleSkillPublish = ({ skill }: ToggleSkillPublishProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async () => {
      await SkillsService.publishSkill({
        skillId: skill.id,
        requestBody: { is_published: !skill.is_published },
      })
    },
    onSuccess: () => {
      showSuccessToast(skill.is_published ? "已下架" : "已上架")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] })
    },
  })

  return (
    <DropdownMenuItem onClick={() => mutation.mutate()}>
      {skill.is_published ? <EyeOff /> : <Eye />}
      {skill.is_published ? "下架" : "上架"}
    </DropdownMenuItem>
  )
}

export default ToggleSkillPublish
